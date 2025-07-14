import streamlit as st
import geopandas as gpd
import folium
from streamlit_folium import st_folium
import pandas as pd
from shapely import wkt

# Load into GeoDataFrame
gdf = gpd.read_file("final_combined_data_with_new_columns.geojson")

st.title("Interactive Store Suitability Heatmap")
st.write("Adjust the weights below to compute a composite suitability score for each ZIP code.")

for col in [
    'total_population', 'median_household_income',
    'pop_under_20','pop_20_30','pop_30_45','pop_45_60','pop_60_plus',
    'low_income','middle_income','high_income',
    'bachelors_or_higher',
    'parking_count',
    'commute_total',
    'hispanic_or_latino','not_hispanic_or_latino','white','black_or_african_american', 'asian'
          ]:
    gdf[col] = pd.to_numeric(gdf[col], errors='coerce').fillna(0) # fill missing values

# list of features
factors = [
    'total_population', 'median_household_income',
    'pop_under_20','pop_20_30','pop_30_45','pop_45_60','pop_60_plus',
    'low_income','middle_income','high_income',
    'bachelors_or_higher',
    'parking_count',
    'commute_total',
    'hispanic_or_latino','not_hispanic_or_latino','white','black_or_african_american', 'asian',
          ]

st.subheader("Set Weights for Each Factor")
# make sliders 0 to 1 for each feature, start at 0
weights = {}
for factor in factors:
    weights[factor] = st.slider(f"Weight for {factor}", 0.0, 1.0, 0.0, step=0.01)

def normalize(series):
    min_val = series.min()
    max_val = series.max()
    if max_val - min_val == 0:
        return series * 0
    return (series - min_val) / (max_val - min_val)

# normalise
for factor in factors:
    norm_col = f"norm_{factor}"
    gdf[norm_col] = normalize(gdf[factor])

# calc composite score using norm vals
total_weight = sum(weights.values())
if total_weight > 0:
    gdf['score'] = sum(weights[factor] * gdf[f"norm_{factor}"] for factor in factors) / total_weight
else:
    gdf['score'] = 0

# Folium map centered on NYC
m = folium.Map(location=[40.7128, -74.0060], zoom_start=10, tiles='cartodbpositron')

# Add a choropleth layer for the composite score
choropleth = folium.Choropleth(
    geo_data=gdf.to_json(),
    data=gdf,
    columns=['ZIP', 'score'],
    key_on='feature.properties.ZIP',
    fill_color='YlOrRd',
    fill_opacity=0.7,
    line_opacity=0.2,
    legend_name='Composite Suitability Score (0-1)'
).add_to(m)

folium.GeoJsonTooltip(
    fields=factors,
    localize=True
).add_to(choropleth.geojson)

# make pointers on the map for the stores
stores_df = pd.read_csv("Retail_Food_Stores.csv")
stores_df['Entity Name'] = stores_df['Entity Name'].str.upper()

tj_df = stores_df[stores_df['Entity Name'].str.contains("TRADER JOE", na=False)]
wf_df = stores_df[stores_df['Entity Name'].str.contains("WHOLE FOODS", na=False)]
wg_df = stores_df[stores_df['Entity Name'].str.contains("WEGMAN", na=False)]

tj_df['geometry'] = tj_df['Georeference'].apply(wkt.loads)
wf_df['geometry'] = wf_df['Georeference'].apply(wkt.loads)
wg_df['geometry'] = wg_df['Georeference'].apply(wkt.loads)

tj_gdf = gpd.GeoDataFrame(tj_df, geometry='geometry', crs="EPSG:4326")
wf_gdf = gpd.GeoDataFrame(wf_df, geometry='geometry', crs="EPSG:4326")
wg_gdf = gpd.GeoDataFrame(wg_df, geometry='geometry', crs="EPSG:4326")

# add score to TJ stores for other computations (mean, std etc)
tj_join = gpd.sjoin(tj_gdf, gdf[['ZIP', 'score', 'geometry']], how='left', predicate='within')

for idx, row in tj_join.iterrows():
    folium.CircleMarker(
        location=[row.geometry.y, row.geometry.x],
        radius=1,
        color='blue',
        fill=True,
        fill_color='blue',
        fill_opacity=0.8,
        popup=f"Trader Joe's: {row['Entity Name']}<br>Score: {row['score']:.2f}"
    ).add_to(m)

for idx, row in wf_gdf.iterrows():
    folium.CircleMarker(
        location=[row.geometry.y, row.geometry.x],
        radius=3,
        color='green',
        fill=True,
        fill_color='green',
        fill_opacity=0.8,
        popup=f"Whole Foods: {row['Entity Name']}"
    ).add_to(m)

for idx, row in wg_gdf.iterrows():
    folium.CircleMarker(
        location=[row.geometry.y, row.geometry.x],
        radius=1,
        color='purple',
        fill=True,
        fill_color='purple',
        fill_opacity=0.8,
        popup=f"Wegmans : {row['Entity Name']}"
    ).add_to(m)

# setup station data, can comment this out (there are a lot of stations can get in the way of the big picture)
stations_df = pd.read_csv("MTA_Subway_Stations.csv")
stations_df = stations_df[['Stop Name', 'GTFS Latitude', 'GTFS Longitude']]
stations_gdf = gpd.GeoDataFrame(
    stations_df,
    geometry=gpd.points_from_xy(stations_df['GTFS Longitude'], stations_df['GTFS Latitude']),
    crs="EPSG:4326"
)

for idx, row in stations_gdf.iterrows():
    folium.CircleMarker(
        location=[row.geometry.y, row.geometry.x],
        radius=0.2,
        color='grey',
        fill=True,
        fill_color='red',
        fill_opacity=0.8,
        popup=f"Station: {row['Stop Name']}"
    ).add_to(m)

# calc TJ stats according to the current scores (from current equation)
avg_score = tj_join['score'].mean()
min_score = tj_join['score'].min()
max_score = tj_join['score'].max()
std_score = tj_join['score'].std()

st.write("Trader Joe's Composite Score Statistics:")
st.write(f"Average: {avg_score:.2f}")
st.write(f"Minimum: {min_score:.2f}")
st.write(f"Maximum: {max_score:.2f}")
st.write(f"Standard Deviation: {std_score:.2f}")


# -------------------------------
# Highlight ZIP 11215 with a custom green style
# -------------------------------
target_zip = "11215"

# for making final visualisation highlighting and marker (for main plot)
# highlight_layer = folium.GeoJson(
#     gdf[gdf['ZIP'] == target_zip].to_json(),
#     style_function=lambda feature: {
#         'fillColor': 'green',
#         'color': 'green',
#         'weight': 2,
#         'fillOpacity': 0.5
#     }
# )
# highlight_layer.add_to(m)

# recommended_location = [40.6665, -73.9950]  # Example coordinates
# folium.Marker(
#     location=recommended_location,
#     popup="Recommended Location in ZIP 11215",
#     icon=folium.Icon(color='green', icon='ok-sign')
# ).add_to(m)

# Display the map in Streamlit
st_data = st_folium(m, width=700, height=500)
