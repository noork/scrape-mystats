# Hockey Stats Scraper

A Python application to scrape, export, store, and visualize hockey player statistics from MyStatsOnline.

## Features

- Scrape tabular hockey player stats from MyStatsOnline
- Export data to CSV and JSON formats
- Store data in SQLite database with timestamps
- Create visualizations and dashboards
- Easy-to-use command-line interface

## Installation

1. Clone or navigate to this directory

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

### Basic Scraping

Run the scraper to fetch data and export to all formats:

```bash
python scraper.py
```

This will:
- Scrape player stats from the configured URL
- Export to timestamped CSV file (e.g., `hockey_stats_20231204_143022.csv`)
- Export to timestamped JSON file (e.g., `hockey_stats_20231204_143022.json`)
- Save to SQLite database (`hockey_stats.db`)
- Display a preview of the data

### Creating Visualizations

After scraping data, create visualizations:

```bash
python visualize.py
```

This creates a `visualizations/` folder with:
- `top_scorers.png` - Bar chart of top point scorers
- `goals_vs_assists.png` - Scatter plot of goals vs assists
- `team_comparison.png` - Team performance comparison
- `stats_distribution.png` - Distribution of goals, assists, and points
- `position_analysis.png` - Stats breakdown by position

## Using the Modules Programmatically

### Scraper Example

```python
from scraper import HockeyStatsScraper

# Initialize scraper
url = "https://www.mystatsonline.com/hockey/visitor/league/stats/skater_hockey.aspx?IDLeague=6894"
scraper = HockeyStatsScraper(url)

# Scrape data
data = scraper.scrape()

# Export to CSV
scraper.export_to_csv("my_stats.csv")

# Export to JSON
scraper.export_to_json("my_stats.json")

# Save to database
scraper.save_to_database("my_database.db")

# Access the data as a pandas DataFrame
print(data.head())
```

### Visualizer Example

```python
from visualize import HockeyStatsVisualizer

# Load from CSV
viz = HockeyStatsVisualizer("hockey_stats_20231204_143022.csv")

# Or load from database
# viz = HockeyStatsVisualizer("hockey_stats.db")

# Or load from DataFrame
# viz = HockeyStatsVisualizer(your_dataframe)

# Create individual visualizations
viz.top_scorers(n=15, output_file='my_top_scorers.png')
viz.goals_vs_assists(output_file='my_scatter.png')

# Or create all visualizations at once
viz.create_dashboard(output_dir='my_visualizations')
```

## Data Schema

The scraped data includes these columns (may vary based on league settings):

- `#` - Player number and name
- `Team` - Team abbreviation
- `POS` - Position
- `GP` - Games Played
- `G` - Goals
- `A` - Assists
- `PTS` - Points
- `PIM` - Penalties in Minutes
- `G/GP` - Goals per Game
- `P/GP` - Points per Game
- `PPG` - Power Play Goals
- `SHG` - Short-Handed Goals
- `OTG` - Overtime Goals
- `ENG` - Empty Net Goals
- `SOG` - Shots on Goal
- `SOS` - Shots on Support
- `WG` - Winning Goals
- `G%` - Goal Percentage
- `HT` - Hat Tricks
- `RATING` - Player Rating

## Database

Data is stored in SQLite with automatic timestamps. Each scrape appends to the database, allowing you to track stats over time.

Query the database:

```python
import sqlite3
import pandas as pd

conn = sqlite3.connect('hockey_stats.db')
df = pd.read_sql_query("SELECT * FROM player_stats ORDER BY scraped_at DESC", conn)
conn.close()
```

## Customization

### Change the URL

Edit the URL in `scraper.py` main function:

```python
url = "https://www.mystatsonline.com/hockey/visitor/league/stats/skater_hockey.aspx?IDLeague=YOUR_LEAGUE_ID"
```

### Modify Visualizations

Edit `visualize.py` to customize:
- Number of top scorers to display
- Chart colors and styles
- Additional metrics to visualize
- Output formats and sizes

## Requirements

- Python 3.7+
- requests
- beautifulsoup4
- pandas
- matplotlib
- seaborn
- lxml

## License

Free to use and modify.
