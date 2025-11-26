import pandas as pd
import geopandas as gpd
import osmnx as ox
import os
import sys

# =====================================================================
# CRITICAL CONFIGURATION: SET THIS TO THE ABSOLUTE PATH
#
# Use the full, absolute path to your METERPOLES folder here.
# Example: r"C:\Users\1striker\OneDrive\Desktop\THESOS\METERPOLES"
BASE_DIRECTORY = r"C:\Users\1striker\OneDrive\Desktop\THESOS\METERPOLES"  
# =====================================================================

# --- Step 1: Load and Consolidate All Meter Poles ---
print("--- Step 1: Loading and Consolidating Meter Poles ---")

# 1. Path Verification and File Listing
if not os.path.isdir(BASE_DIRECTORY):
    print(f"\n🚨 CRITICAL ERROR: The directory '{BASE_DIRECTORY}' does not exist.")
    print("Please check the absolute path set in the BASE_DIRECTORY variable.")
    print(f"Current Working Directory (CWD): {os.getcwd()}")
    sys.exit()

file_numbers = range(1, 12) 
expected_files = [f"poleblock{i}.csv" for i in file_numbers]
data_frames = []
files_found = 0

print(f"Checking for files in: {BASE_DIRECTORY}")
print("-" * 50)


for filename in expected_files:
    full_path = os.path.join(BASE_DIRECTORY, filename)
    
    try:
        df = pd.read_csv(full_path, skipinitialspace=True)
        
        if 'BLOCK ' in df.columns:
            df = df.rename(columns={'BLOCK ': 'BLOCK'})
            
        data_frames.append(df)
        files_found += 1
        
    except FileNotFoundError:
        print(f"❌ File Not Found Error: Could not find {full_path}")
        continue
    except Exception as e:
        print(f"❌ An unexpected error occurred while reading {filename}: {e}")
        continue

if files_found == 0:
    print("\n🚨 CRITICAL ERROR: NO METER POLE FILES WERE LOADED.")
    print("Double-check the BASE_DIRECTORY and the file names.")
    sys.exit()

poles_df = pd.concat(data_frames, ignore_index=True)

# 2. Parse the 'POLE_LOC' string ("Latitude, Longitude")
poles_df['POLE_LOC'] = poles_df['POLE_LOC'].astype(str).str.replace('"', '')
poles_df[['latitude', 'longitude']] = poles_df['POLE_LOC'].str.split(', ', expand=True)

# Convert coordinates and drop nulls
poles_df['latitude'] = pd.to_numeric(poles_df['latitude'], errors='coerce')
poles_df['longitude'] = pd.to_numeric(poles_df['longitude'], errors='coerce')
poles_df.dropna(subset=['latitude', 'longitude'], inplace=True)

# 3. Create a unique identifier for each pole
poles_df['POLE_ID'] = poles_df['BLOCK'].astype(str) + '-' + poles_df['NUMBER'].astype(str)

# 4. Convert the DataFrame to a GeoDataFrame
poles_gdf = gpd.GeoDataFrame(
    poles_df,
    geometry=gpd.points_from_xy(poles_df.longitude, poles_df.latitude),
    crs="EPSG:4326"
)

print(f"✅ Successfully loaded and combined {len(poles_gdf)} meter poles from {files_found} files.")
print("-" * 50)


# --- Step 2: Download and Process the Road Network ---
print("--- Step 2: Downloading the Road Network ---")

center_lat = poles_gdf['latitude'].mean()
center_lon = poles_gdf['longitude'].mean()
search_dist_m = 2000

print(f"⬇️ Downloading driving network centered at ({center_lat:.4f}, {center_lon:.4f}) with a {search_dist_m}m radius...")

G = ox.graph_from_point(
    (center_lat, center_lon), 
    dist=search_dist_m, 
    network_type="drive"
)

# Project the graph for accurate metric measurements
G_proj = ox.project_graph(G) 
G_proj = ox.add_edge_speeds(G_proj)
G_proj = ox.add_edge_travel_times(G_proj)

print(f"✅ Downloaded and processed graph with {G_proj.number_of_nodes()} intersections and {G_proj.number_of_edges()} road segments.")
print("-" * 50)


# --- Step 3: Snap Poles to the Road Network ---
print("--- Step 3: Snapping Poles to the Road Network ---")

all_lons = poles_gdf.geometry.x.values
all_lats = poles_gdf.geometry.y.values

# This requires the installed 'scipy' dependency
nearest_node_ids = ox.nearest_nodes(G_proj, all_lons, all_lats)

poles_gdf['nearest_node_id'] = nearest_node_ids

print("✅ Successfully snapped all poles to the nearest road network intersection.")
print("-" * 50)


# --- Step 4: Export to GeoJSON (FIXED: Reprojection Added) ---
print("--- Step 4: Exporting to GeoJSON (Reprojecting for Web Map Compatibility) ---")

output_dir = "OUTPUT_GEOJSON"
os.makedirs(output_dir, exist_ok=True) 

# 1. Convert the projected graph to GeoDataFrames
gdf_nodes_proj, gdf_edges_proj = ox.graph_to_gdfs(G_proj)

# 🚨 FIX: Reproject road network GeoDataFrames back to WGS 84 (EPSG:4326) for GeoJSON export
gdf_nodes = gdf_nodes_proj.to_crs(epsg=4326)
gdf_edges = gdf_edges_proj.to_crs(epsg=4326)

# 2. Export Nodes GeoJSON
gdf_nodes.to_file(
    os.path.join(output_dir, "road_network_nodes.geojson"),
    driver='GeoJSON',
    encoding="utf-8"
)
print(f"💾 Exported road network nodes to '{output_dir}/road_network_nodes.geojson'")

# 3. Export Edges GeoJSON
gdf_edges.to_file(
    os.path.join(output_dir, "road_network_edges.geojson"),
    driver='GeoJSON',
    encoding="utf-8"
)
print(f"💾 Exported road network edges to '{output_dir}/road_network_edges.geojson'")

# 4. Export the Snapped Meter Poles GeoDataFrame (already in EPSG:4326)
poles_gdf[['POLE_ID', 'BLOCK', 'NUMBER', 'nearest_node_id', 'geometry']].to_file(
    os.path.join(output_dir, "meter_poles_snapped.geojson"), 
    driver='GeoJSON',   
    encoding="utf-8"
)
print(f"💾 Exported meter poles to '{output_dir}/meter_poles_snapped.geojson'")
print("-" * 50)

print("✨ COMPLETE: All GeoJSON files are saved in the 'OUTPUT_GEOJSON' folder. You can now open your HTML map!")