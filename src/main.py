from dataclasses import dataclass
from flask import Flask, render_template, send_from_directory, jsonify, request
import os
import json
import math
from collections import defaultdict
import heapq
from typing import Dict, List, Set, Tuple, Optional

current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(current_dir)
data_dir = os.path.join(root_dir, 'data')

app = Flask(__name__, template_folder=os.path.join(root_dir, 'src', 'templates'))

TRANSFER_COST = 2.0
TRANSFER_DISTANCE_PENALTY = 0.5

def load_stations() -> List[Dict]:
    path = os.path.join(data_dir, 'stations.json')
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data['features']

def load_transfer_rules() -> List[Dict]:
    path = os.path.join(data_dir, 'transfer_rules.json')
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data['transfers']

def calculate_distance(coord1: Tuple[float, float], coord2: Tuple[float, float]) -> float:
    lon1, lat1 = coord1
    lon2, lat2 = coord2
    
    R = 6371.0  
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    return R * c

def calculate_heuristic(graph: Dict, current: str, goal: str) -> float:
    coord1 = graph[current]['coords']
    coord2 = graph[goal]['coords']
    return calculate_distance(coord1, coord2)

def _create_path_details(path_tuples: List[Tuple[str, str]]) -> List[str]:
    details = []
    start_station, start_line = path_tuples[0]
    details.append(f"🏁 <b>Start:</b> {start_station} ({start_line})")
    
    for i in range(1, len(path_tuples)):
        current_station, current_line = path_tuples[i]
        prev_station, prev_line = path_tuples[i-1]
        
        if current_line != prev_line:
            details.append(f"Transfer at {current_station}:")
            details.append(f"<b>  • From: </b> {prev_line}")
            details.append(f"<b> • To: </b> {current_line}")
            
    end_station, end_line = path_tuples[-1]
    details.append(f"<b>Destination:</b> {end_station} ({end_line})")
    
    return details
class PriorityQueue:
    def __init__(self):
        self._queue = []
        self._entry_finder = {}
        self._counter = 0
        self._REMOVED = '<removed>'
        
    def empty(self) -> bool:
        return not self._entry_finder

    def put(self, item: Tuple[str, str], priority: float) -> None:
        if item in self._entry_finder:
            self.remove(item)
        entry = [priority, self._counter, item]
        self._entry_finder[item] = entry
        heapq.heappush(self._queue, entry)
        self._counter += 1

    def remove(self, item: Tuple[str, str]) -> None:
        entry = self._entry_finder.pop(item)
        entry[-1] = self._REMOVED

    def get(self) -> Tuple[str, str]:
        while self._queue:
            priority, count, item = heapq.heappop(self._queue)
            if item is not self._REMOVED:
                del self._entry_finder[item]
                return item
        raise KeyError('get from empty priority queue')

class TransferCache:
    def __init__(self, transfer_rules: List[Dict]):
        self._cache = set()
        for rule in transfer_rules:
            self._cache.add((
                rule['stationA'], rule['lineA'],
                rule['stationB'], rule['lineB']
            ))
            self._cache.add((
                rule['stationB'], rule['lineB'],
                rule['stationA'], rule['lineA']
            ))

    def is_valid_transfer(self, stA: str, lineA: str, stB: str, lineB: str) -> bool:
        if lineA == lineB:
            return True
        return (stA, lineA, stB, lineB) in self._cache

    @staticmethod
    def create_station_graph(features: List[Dict]) -> Dict:
        graph: Dict[str, Dict] = {}

        for f in features:
            st_name = f['properties']['ISTASYON']
            line_name = f['properties']['PROJE_ADI']
            coords = f['geometry']['coordinates']

            if st_name not in graph:
                graph[st_name] = {
                    'coords': coords,
                    'lines': set([line_name]),
                    'connections': []
                }
            else:
                graph[st_name]['lines'].add(line_name)

        stations_by_line = defaultdict(list)
        for f in features:
            line = f['properties']['PROJE_ADI']
            st_name = f['properties']['ISTASYON']
            order_val = f['properties'].get('order', 9999)
            stations_by_line[line].append((st_name, order_val))

        for line, st_list in stations_by_line.items():
            st_list.sort(key=lambda x: x[1])
            for i in range(len(st_list) - 1):
                stationA = st_list[i][0]
                stationB = st_list[i+1][0]
                graph[stationA]['connections'].append((stationB, line))
                graph[stationB]['connections'].append((stationA, line))

        transfers = load_transfer_rules()
        for rule in transfers:
            stA, lineA = rule['stationA'], rule['lineA']
            stB, lineB = rule['stationB'], rule['lineB']

            if stA in graph and stB in graph:
                graph[stA]['connections'].append((stB, lineB))
                graph[stB]['connections'].append((stA, lineA))

        return graph

class AStarPathfinder:
    def __init__(self, graph: Dict, transfer_cache: TransferCache):
        self.graph = graph
        self.transfer_cache = transfer_cache
        self.frontier = PriorityQueue()
        self.g_scores: Dict[Tuple[str, str], float] = {}
        self.came_from: Dict[Tuple[str, str], Optional[Tuple[str, str]]] = {}
        self.transfer_counts: Dict[Tuple[str, str], int] = {}
        
    def _calculate_cost(self, current_station: str, current_line: str, 
                       next_station: str, next_line: str) -> float:
        dist = calculate_distance(
            self.graph[current_station]['coords'],
            self.graph[next_station]['coords']
        )
        if current_line != next_line:
            return dist * TRANSFER_COST + TRANSFER_DISTANCE_PENALTY
        return dist

    def find_path(self, start: str, goal: str, 
                 end_line: Optional[str] = None
                 ) -> Tuple[Optional[List[str]], Optional[List[str]], 
                          Optional[float], Optional[int]]:
        if start not in self.graph or goal not in self.graph:
            return None, None, None, None

        self.frontier = PriorityQueue()
        self.g_scores.clear()
        self.came_from.clear()
        self.transfer_counts.clear()
        explored: Set[Tuple[str, str]] = set()

        for start_line in self.graph[start]['lines']:
            start_state = (start, start_line)
            self.g_scores[start_state] = 0.0
            self.came_from[start_state] = None
            self.transfer_counts[start_state] = 0
            h_score = calculate_heuristic(self.graph, start, goal)
            self.frontier.put(start_state, h_score)

        final_state = None

        while not self.frontier.empty():
            current_state = self.frontier.get()
            current_station, current_line = current_state

            if current_station == goal:
                if end_line is None or current_line == end_line:
                    final_state = current_state
                    break

            if current_state in explored:
                continue
            explored.add(current_state)

            for next_station, next_line in self.graph[current_station]['connections']:
                if not self.transfer_cache.is_valid_transfer(
                    current_station, current_line,
                    next_station, next_line
                ):
                    continue

                next_state = (next_station, next_line)
                if next_state in explored:
                    continue

                cost = self._calculate_cost(current_station, current_line,
                                         next_station, next_line)
                tentative_g = self.g_scores[current_state] + cost

                if (next_state not in self.g_scores or 
                    tentative_g < self.g_scores[next_state]):
                    
                    self.g_scores[next_state] = tentative_g
                    self.came_from[next_state] = current_state
                    self.transfer_counts[next_state] = (
                        self.transfer_counts[current_state] + 
                        (1 if current_line != next_line else 0)
                    )

                    h_score = calculate_heuristic(self.graph, next_station, goal)
                    f_score = tentative_g + h_score
                    self.frontier.put(next_state, f_score)

        if not final_state:
            return None, None, None, None

        path = self._reconstruct_path(final_state)
        stations = [s for (s, _) in path]
        details = _create_path_details(path)
        distance = self.g_scores[final_state]
        transfers = self.transfer_counts[final_state]

        return stations, details, distance, transfers

    def _reconstruct_path(self, final_state: Tuple[str, str]) -> List[Tuple[str, str]]:
        path = []
        current = final_state
        while current:
            path.append(current)
            current = self.came_from[current]
        return list(reversed(path))

@app.route('/')
def index():
    return render_template('map.html')

@app.route('/data/stations.json')
def serve_stations():
    return send_from_directory(data_dir, 'stations.json')

@app.route('/api/search_stations')
def search_stations():
    query = request.args.get('query', '').lower()
    if len(query) < 2:
        return jsonify([])

    feats = load_stations()
    results = []
    for f in feats:
        st_name = f['properties']['ISTASYON'].lower()
        line_name = f['properties']['PROJE_ADI']
        if query in st_name:
            results.append([f['properties']['ISTASYON'], line_name])
    return jsonify(results)

@app.route('/api/find_route')
def api_find_route():
    start = request.args.get('start')
    end = request.args.get('end')
    end_line = request.args.get('end_line')

    if not start or not end:
        return jsonify({"error": "Missing start or end station"}), 400

    features = load_stations()
    transfer_cache = TransferCache(load_transfer_rules())
    graph = transfer_cache.create_station_graph(features)
    
    pathfinder = AStarPathfinder(graph, transfer_cache)
    path, details, distance, transfers = pathfinder.find_path(start, end, end_line)

    if not path:
        return jsonify({"error": "No route found"}), 404

    response_data: Dict[str, Any] = {
        "path": path,
        "details": details,
        "distance": distance,
        "transfers": transfers
    }
    return jsonify(response_data)

if __name__ == '__main__':
    app.run(debug=True)