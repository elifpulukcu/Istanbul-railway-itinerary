# Istanbul Railway Itinerary

This repository provides a Flask-based web application for planning itineraries across Istanbul’s railway network, including metro, tram, funicular, and cable car lines. The application displays a Leaflet map of Istanbul and allows users to search for stations, calculate routes, and get detailed step-by-step directions, transfers, and distance information.

## Overview

This project aims to offer a **multi-modal itinerary planner** for the Istanbul railway network. It leverages a JSON dataset of stations and transfer rules to compute routes using an **A\* pathfinding** algorithm. The resulting itinerary displays station-by-station progression, including any necessary line transfers.

However, obtaining up-to-date data from the **[IBB Open Data Portal](https://data.ibb.gov.tr/en/dataset/rayli-sistem-istasyon-noktalari-verisi/resource/3dc8203f-3613-48a8-85e9-24fffb7821ad?view_id%3D32d900ee-7ed4-4ed2-a4a6-be53ab1fc02e)** proved challenging. Many lines, especially newly opened routes (e.g., **M11**), are not yet reflected in older datasets. To address this, I used recently updated GeoJSON files that provide the geospatial locations of many lines and leveraged them to build the lines and transfer points for this planner. Consequently, I created a custom `transfer_rules.json` file to define valid interchange stations. If you need this custom file or have questions about how it was constructed, please reach out.

You can watch the project video [here](https://drive.google.com/file/d/1Yn46T1qA9aPNmqeLEwgGaMpTx37p_nQV/view?usp=share_link).

## Features

1. **Leaflet Map Integration**  
   - Displays a stylized map of Istanbul.
   - Each railway line is color-coded.
   - Stations are rendered as circle markers with interactive popups.

2. **Interactive Station Search**  
   - Type-ahead functionality to filter stations by name.
   - Dropdown suggestions appear dynamically as the user types.

3. **Route Computation**  
   - **A\* Algorithm**: Tailored for railway lines with a geographic distance heuristic (Haversine formula).  
   - **Custom Transfer Costs**: Assigns a higher cost to line transfers, minimizing unnecessary changes.  
   - **Distance & Transfers**: Outputs the total travel distance (in km) and the number of transfers.

4. **Detailed Itinerary**  
   - Textual route breakdown with station-by-station details.  
   - Start and end stations, transfer points, total distance, and transfer count are all included.

5. **API Endpoints**  
   - Supports station searching and route retrieval via JSON responses.

## Project Structure

A high-level view of the repository’s structure:

```
Istanbul-railway-itinerary/
├── data/
│   ├── stations.json          # All railway stations with coordinates & line info
│   └── transfer_rules.json    # Rules for allowed transfers between lines
├── Istanbul-env/              # (Optional) Python virtual environment directory (not tracked by Git)
├── src/
│   ├── main.py                # Flask application and route definitions (entry point)
│   └── templates/
│       └── map.html           # Main HTML template for rendering the map
├── .gitignore                 # Files/folders to be ignored by Git
├── README.md                  # Project documentation
└── requirements.txt           # Python dependencies
```

### Notable Files

- **`main.py`**  
  Contains the main Flask application, including:
  - URL routes  
  - A\* route-finding logic  
  - Data loading for stations and transfer rules  

- **`stations.json`**  
  GeoJSON file containing station coordinates, line information, and related metadata.

- **`transfer_rules.json`**  
  Specifies valid line-to-line transfer points, used by the A\* algorithm to compute feasible routes.

## Installation

1. **Clone the Repository**
   ```bash
   git clone https://github.com/elifpulukcu/Istanbul-railway-itinerary.git
   ```

2. **Change into the Project Directory**
   ```bash
   cd Istanbul-railway-itinerary
   ```

3. **Create and Activate a Virtual Environment (Recommended)**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Linux/Mac
   venv\Scripts\activate     # On Windows
   ```

4. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

5. **Run the Application**
   ```bash
   python main.py
   ```

6. **Access the Application**
   - Open your web browser and go to the displayed URL in the console.

## Usage

1. **Launch the Flask App**  
   Run `python main.py` from your terminal or command prompt.

2. **Open the Map Interface**  
   Navigate to the app’s URL (e.g., `http://127.0.0.1:5000/`).

3. **Select Start and End Stations**  
   - Enter station names in the search fields.
   - Choose a station from the dropdown suggestions.

4. **Find Route**  
   - Click **"Find Route"** to compute the best path.
   - View station-by-station directions, transfer points, total distance, and transfer count.

5. **Animated Marker**  
   - The route is animated on the map for improved visualization.

## API Endpoints

### 1. `GET /api/search_stations`
- **Query Parameters**:  
  - `query`: Partial station name (at least 2 characters).
    
- **Response**:  
  JSON array of matching stations in the format:
  ```json
  [
    ["StationName1", "LineName1"],
    ["StationName2", "LineName2"]
  ]
  ```
- **Example**:
  ```bash
  curl "http://127.0.0.1:5000/api/search_stations?query=yen"
  ```

### 2. `GET /api/find_route`
- **Query Parameters**:  
  - `start`: Starting station name.  
  - `end`: Destination station name.  
  - `end_line` (optional): Destination line if you prefer to arrive on a specific line.
    
- **Response**:  
  JSON object containing:
  ```json
  {
    "path": ["StationA", "StationB", "StationC"],
    "details": [
      "🏁 <b>Start:</b> StationA (LineX)",
      "...",
      "<b>Destination:</b> StationC (LineY)"
    ],
    "distance": 10.23,
    "transfers": 2
  }
  ```
- **Example**:
  ```bash
  curl "http://127.0.0.1:5000/api/find_route?start=Yenikapı&end=Hacıosman"
  ```

## License

This project is distributed under the **MIT License**. See [LICENSE](LICENSE) for more information.

---

## Author

Developed by [Elif Pulukçu](https://github.com/elifpulukcu).

If you have any questions or would like to contribute, feel free to open an issue or create a pull request.  

---  

*Thank you for checking out the Istanbul Railway Itinerary project!*
