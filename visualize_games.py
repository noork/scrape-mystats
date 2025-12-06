#!/usr/bin/env python3
"""
Script to visualize closest games from games data
"""
import glob
from visualize import GamesVisualizer
from pathlib import Path


def main():
    # Find the most recent games CSV file
    csv_files = glob.glob('output/games_*.csv')

    if not csv_files:
        print("No games CSV files found. Run games_scraper.py first.")
        return

    # Use the most recent file
    latest_file = max(csv_files)
    print(f"Loading games data from {latest_file}")

    # Create visualizer
    viz = GamesVisualizer(latest_file)

    # Ensure output directory exists
    Path("output/visualizations").mkdir(parents=True, exist_ok=True)

    # Generate closest games visualization
    print("\nGenerating closest games visualization...")
    closest_games = viz.closest_games(
        output_file='output/visualizations/closest_games.png',
        top_n=30
    )

    # Print summary
    if closest_games is not None:
        print("\n" + "="*60)
        print("CLOSEST GAMES SUMMARY")
        print("="*60)
        print(f"Total completed games: {len(viz.data.dropna(subset=['Away Score', 'Home Score']))}")
        print(f"Showing top {len(closest_games)} closest games")
        print(f"Games with 0 differential (ties): {len(closest_games[closest_games['Score Differential'] == 0])}")
        print(f"Games with 1 goal differential: {len(closest_games[closest_games['Score Differential'] == 1])}")
        print(f"Games with 2 goal differential: {len(closest_games[closest_games['Score Differential'] == 2])}")
        print("="*60)


if __name__ == "__main__":
    main()
