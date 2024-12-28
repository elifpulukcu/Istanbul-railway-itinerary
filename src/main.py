from flask import Flask, render_template, send_from_directory, jsonify
import json
from collections import defaultdict
import math
import heapq
import os

current_dir = os.path.dirname(os.path.abspath(__file__))
data_dir = os.path.join(os.path.dirname(current_dir), 'data')

app = Flask(__name__)

TRANSFER_COST = 2.0  
TRANSFER_DISTANCE_PENALTY = 0.5  

def load_stations():
    with open(os.path.join(data_dir, 'stations.json')) as f:
        data = json.load(f)
    return data['features']

def calculate_distance(coord1, coord2):
    lon1, lat1 = map(math.radians, coord1)
    lon2, lat2 = map(math.radians, coord2)
    
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    r = 6371
    
    return c * r

def calculate_edge_cost(graph, station1, station2):
    distance = calculate_distance(graph[station1]['coords'], graph[station2]['coords'])
    
    if graph[station1]['line'] != graph[station2]['line']:
        return (distance * TRANSFER_COST) + TRANSFER_DISTANCE_PENALTY
    
    return distance

def find_nearest_station(current_coord, remaining_stations):
    if not remaining_stations:
        return None
    distances = [(station, calculate_distance(current_coord, station['geometry']['coordinates']))
                for station in remaining_stations]
    return min(distances, key=lambda x: x[1])[0]

def create_route_graph():
    features = load_stations()
    routes = defaultdict(list)
    project_stations = defaultdict(list)
    for feature in features:
        project_name = feature['properties']['PROJE_ADI']
        project_stations[project_name].append(feature)

    for project_name, stations in project_stations.items():
        if not stations:
            continue
        remaining = stations.copy()
        current = min(stations, key=lambda x: sum(x['geometry']['coordinates']))
        remaining.remove(current)
        ordered_stations = [current]

        while remaining:
            current_coord = current['geometry']['coordinates']
            nearest = find_nearest_station(current_coord, remaining)
            if nearest:
                ordered_stations.append(nearest)
                remaining.remove(nearest)
                current = nearest

        routes[project_name] = [station['properties']['ISTASYON'] for station in ordered_stations]
    return routes, features

def create_station_graph(features):
    graph = {}
    for feature in features:
        station_name = feature['properties']['ISTASYON']
        coords = feature['geometry']['coordinates']
        if station_name not in graph:
            graph[station_name] = {
                'coords': coords,
                'connections': [],
                'line': feature['properties']['PROJE_ADI']
            }

    routes, _ = create_route_graph()
    for line_name, stations in routes.items():
        for i in range(len(stations) - 1):
            graph[stations[i]]['connections'].append(stations[i + 1])
            graph[stations[i + 1]]['connections'].append(stations[i])

    return graph

def heuristic(graph, station1, station2):
    return calculate_distance(graph[station1]['coords'], graph[station2]['coords'])

def find_path(graph, start, goal):
    if start not in graph or goal not in graph:
        return None, None, None, None

    frontier = [(0, start, [])]  # Priority queue for A*
    heapq.heapify(frontier)
    came_from = {start: None}
    cost_so_far = {start: 0}  # g(n) in A* algorithm
    transfers_count = {start: 0}  # Keep track of number of transfers
    
    while frontier:
        current_cost, current, path = heapq.heappop(frontier)
        
        if current == goal:
            final_path = path + [current]
            total_distance = sum(calculate_distance(graph[final_path[i]]['coords'], 
                                                 graph[final_path[i+1]]['coords']) 
                               for i in range(len(final_path)-1))
            return final_path, get_route_details(graph, final_path), total_distance, transfers_count[current]
            
        for next_station in graph[current]['connections']:
            edge_cost = calculate_edge_cost(graph, current, next_station)
            new_cost = cost_so_far[current] + edge_cost
            
            new_transfers = transfers_count[current]
            if len(path) > 0 and graph[current]['line'] != graph[next_station]['line']:
                new_transfers += 1
            
            if next_station not in cost_so_far or new_cost < cost_so_far[next_station]:
                cost_so_far[next_station] = new_cost
                transfers_count[next_station] = new_transfers
                # f(n) = g(n) + h(n)
                priority = new_cost + heuristic(graph, next_station, goal)
                heapq.heappush(frontier, (priority, next_station, path + [current]))
                came_from[next_station] = current
    
    return None, None, None, None

def get_route_details(graph, path):
    details = []
    current_line = None
    transfers = 0
    
    for i in range(len(path)):
        station = path[i]
        line = graph[station]['line']
        
        if i == 0:
            details.append(f"{station} ({line})")
            current_line = line
            continue
            
        if line != current_line:
            transfers += 1
            details.append(f"↓ TRANSFER: {station}")
            details.append(f"  {station} ({line})")
            current_line = line
        else:
            details.append(f"→ {station} ({line})")
    
    return details

def search_stations(graph, query):
    matches = []
    for station in graph:
        if query.lower() in station.lower():
            matches.append(station)
    return matches

@app.route('/')
def show_map():
    return render_template('map.html')

@app.route('/data/stations.json')
def serve_stations():
    return send_from_directory(data_dir, 'stations.json')

@app.route('/api/search/<query>')
def search_station_api(query):
    _, features = create_route_graph()
    graph = create_station_graph(features)
    matches = search_stations(graph, query)
    return jsonify(matches)

@app.route('/api/route/<start>/<end>')
def find_route_api(start, end):
    _, features = create_route_graph()
    graph = create_station_graph(features)
    path, details, distance, transfers = find_path(graph, start, end)
    if path:
        return jsonify({
            'success': True,
            'path': path,
            'details': details,
            'distance': distance,
            'transfers': transfers
        })
    return jsonify({'success': False, 'message': 'Route not found'})

def cli_mode():
    """Command line interface mode"""
    _, features = create_route_graph()
    graph = create_station_graph(features)
    
    while True:
        start_query = input("\nEnter starting station (q to quit): ")
        if start_query.lower() == 'q':
            break
            
        start_matches = search_stations(graph, start_query)
        if not start_matches:
            print("Starting station not found.")
            continue
            
        if len(start_matches) > 1:
            print("\nMultiple stations found:")
            for i, station in enumerate(start_matches, 1):
                print(f"{i}. {station} ({graph[station]['line']})")
            choice = int(input("Which station would you like to choose? (enter number): ")) - 1
            start_station = start_matches[choice]
        else:
            start_station = start_matches[0]
            
        end_query = input("Enter destination station: ")
        end_matches = search_stations(graph, end_query)
        
        if not end_matches:
            print("Destination station not found.")
            continue
            
        if len(end_matches) > 1:
            print("\nMultiple stations found:")
            for i, station in enumerate(end_matches, 1):
                print(f"{i}. {station} ({graph[station]['line']})")
            choice = int(input("Which station would you like to choose? (enter number): ")) - 1
            end_station = end_matches[choice]
        else:
            end_station = end_matches[0]
            
        path, details, total_distance, num_transfers = find_path(graph, start_station, end_station)
        
        if path:
            print("\nShortest route:")
            for detail in details:
                print(detail)
            print(f"\nTotal distance: {total_distance:.2f} km")
            print(f"Number of transfers: {num_transfers}")
        else:
            print("\nNo route found.")

if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == 'cli':
        cli_mode()
    else:
        app.run(debug=True, port=5000)