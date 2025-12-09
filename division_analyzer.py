#!/usr/bin/env python3
"""
Division Analyzer - Determine fair division assignments based on team performance

This tool calculates team strength metrics and suggests balanced division assignments.
"""
import pandas as pd
import numpy as np
from pathlib import Path
import matplotlib.pyplot as plt
import seaborn as sns


class DivisionAnalyzer:
    def __init__(self, games_file, standings_file=None):
        """
        Initialize analyzer with games data and optional standings data

        Args:
            games_file: Path to games CSV file
            standings_file: Optional path to team standings CSV file
        """
        self.games = pd.read_csv(games_file)
        self.standings = pd.read_csv(standings_file) if standings_file else None
        self._prepare_data()

    def _prepare_data(self):
        """Clean and prepare the data"""
        # Convert scores to numeric
        self.games['Away Score'] = pd.to_numeric(self.games['Away Score'], errors='coerce')
        self.games['Home Score'] = pd.to_numeric(self.games['Home Score'], errors='coerce')

        # Filter only completed games
        self.completed_games = self.games.dropna(subset=['Away Score', 'Home Score']).copy()

        # Add score differential
        self.completed_games['Score Differential'] = (
            self.completed_games['Home Score'] - self.completed_games['Away Score']
        )

    def filter_games(self, start_date=None, end_date=None, exclude_dates=None, min_date=None, max_date=None):
        """
        Filter games based on date criteria

        Args:
            start_date: Include games on or after this date
            end_date: Include games on or before this date
            exclude_dates: List of dates to exclude
            min_date: Alternative name for start_date
            max_date: Alternative name for end_date

        Returns:
            Filtered DataFrame
        """
        filtered = self.completed_games.copy()

        if start_date or min_date:
            date_filter = start_date or min_date
            filtered = filtered[filtered['Date'] >= date_filter]

        if end_date or max_date:
            date_filter = end_date or max_date
            filtered = filtered[filtered['Date'] <= date_filter]

        if exclude_dates:
            filtered = filtered[~filtered['Date'].isin(exclude_dates)]

        return filtered

    def calculate_team_metrics(self, games_df=None):
        """
        Calculate comprehensive team performance metrics

        Args:
            games_df: Optional filtered games dataframe, defaults to all completed games

        Returns:
            DataFrame with team metrics
        """
        if games_df is None:
            games_df = self.completed_games

        teams = []
        metrics = []

        # Get unique team names (prefer Team Name over raw team name)
        all_teams = set()
        for col in ['Away Team Name', 'Home Team Name']:
            if col in games_df.columns:
                all_teams.update(games_df[col].dropna().unique())

        # Fallback to raw team names if Team Name columns don't exist
        if not all_teams:
            all_teams.update(games_df['Away Team'].dropna().unique())
            all_teams.update(games_df['Home Team'].dropna().unique())

        for team in all_teams:
            # Find games for this team
            if 'Away Team Name' in games_df.columns:
                away_games = games_df[games_df['Away Team Name'] == team]
                home_games = games_df[games_df['Home Team Name'] == team]
            else:
                away_games = games_df[games_df['Away Team'] == team]
                home_games = games_df[games_df['Home Team'] == team]

            # Calculate metrics
            games_played = len(away_games) + len(home_games)

            if games_played == 0:
                continue

            # Goals
            goals_for = (away_games['Away Score'].sum() + home_games['Home Score'].sum())
            goals_against = (away_games['Home Score'].sum() + home_games['Away Score'].sum())

            # Wins/Losses/Ties
            away_wins = (away_games['Away Score'] > away_games['Home Score']).sum()
            home_wins = (home_games['Home Score'] > home_games['Away Score']).sum()
            wins = away_wins + home_wins

            away_losses = (away_games['Away Score'] < away_games['Home Score']).sum()
            home_losses = (home_games['Home Score'] < home_games['Away Score']).sum()
            losses = away_losses + home_losses

            ties = games_played - wins - losses

            # Points (assuming 2 for win, 1 for tie, 0 for loss)
            points = wins * 2 + ties * 1

            # Win percentage
            win_pct = wins / games_played if games_played > 0 else 0

            # Goal differential
            goal_diff = goals_for - goals_against

            # Goals per game
            gpg = goals_for / games_played if games_played > 0 else 0
            gapg = goals_against / games_played if games_played > 0 else 0

            # Strength rating (combination of win% and goal differential)
            strength = (win_pct * 100) + (goal_diff / games_played)

            teams.append(team)
            metrics.append({
                'Team': team,
                'GP': games_played,
                'W': wins,
                'L': losses,
                'T': ties,
                'Points': points,
                'Win %': round(win_pct * 100, 1),
                'GF': int(goals_for),
                'GA': int(goals_against),
                'GD': int(goal_diff),
                'GPG': round(gpg, 2),
                'GAPG': round(gapg, 2),
                'Strength': round(strength, 2)
            })

        df = pd.DataFrame(metrics)
        df = df.sort_values('Strength', ascending=False).reset_index(drop=True)

        return df

    def suggest_divisions(self, team_metrics, num_divisions=5, division_names=None):
        """
        Suggest balanced division assignments using snake draft method

        Args:
            team_metrics: DataFrame with team metrics
            num_divisions: Number of divisions (default 5)
            division_names: Optional list of division names (default A, B, C, D, E, etc.)

        Returns:
            DataFrame with suggested division assignments
        """
        if division_names is None:
            division_names = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H'][:num_divisions]

        # Sort teams by strength (already sorted in calculate_team_metrics)
        teams = team_metrics.copy()

        # Snake draft assignment
        divisions = {name: [] for name in division_names}
        division_strengths = {name: 0 for name in division_names}

        # Use snake draft: 1,2,3,4,5,5,4,3,2,1,1,2,3...
        division_order = []
        forward = True
        while len(division_order) < len(teams):
            if forward:
                division_order.extend(division_names)
            else:
                division_order.extend(reversed(division_names))
            forward = not forward

        # Assign teams
        for i, (_, team_row) in enumerate(teams.iterrows()):
            if i >= len(division_order):
                break
            div = division_order[i]
            divisions[div].append(team_row.to_dict())
            division_strengths[div] += team_row['Strength']

        # Create output dataframe
        results = []
        for div_name, div_teams in divisions.items():
            for team in div_teams:
                team['Suggested Division'] = div_name
                results.append(team)

        result_df = pd.DataFrame(results)

        # Add current division if available
        if self.standings is not None and 'Division' in self.standings.columns:
            # Create mapping from team name to current division
            current_div_map = {}
            for _, row in self.standings.iterrows():
                team_name = row.get('Team Name', row.get('Team', ''))
                if team_name:
                    current_div_map[team_name] = row['Division']

            result_df['Current Division'] = result_df['Team'].map(current_div_map)

        return result_df, division_strengths

    def visualize_divisions(self, division_assignments, division_strengths, output_file='division_balance.png'):
        """
        Visualize the division assignments and balance

        Args:
            division_assignments: DataFrame with team assignments
            division_strengths: Dictionary of division total strengths
            output_file: Path to save visualization
        """
        fig, axes = plt.subplots(2, 2, figsize=(16, 12))

        # 1. Strength by Division (box plot)
        ax1 = axes[0, 0]
        division_assignments.boxplot(column='Strength', by='Suggested Division', ax=ax1)
        ax1.set_title('Team Strength Distribution by Division')
        ax1.set_xlabel('Division')
        ax1.set_ylabel('Strength Rating')
        plt.sca(ax1)
        plt.xticks(rotation=0)

        # 2. Total Division Strength (bar chart)
        ax2 = axes[0, 1]
        divs = sorted(division_strengths.keys())
        strengths = [division_strengths[d] for d in divs]
        bars = ax2.bar(divs, strengths)
        ax2.set_title('Total Division Strength')
        ax2.set_xlabel('Division')
        ax2.set_ylabel('Total Strength')
        ax2.axhline(np.mean(strengths), color='red', linestyle='--', label=f'Average: {np.mean(strengths):.1f}')
        ax2.legend()

        # Color bars by relative strength
        max_strength = max(strengths)
        min_strength = min(strengths)
        for bar, strength in zip(bars, strengths):
            normalized = (strength - min_strength) / (max_strength - min_strength) if max_strength != min_strength else 0.5
            bar.set_color(plt.cm.RdYlGn(normalized))

        # 3. Team Count by Division
        ax3 = axes[1, 0]
        team_counts = division_assignments['Suggested Division'].value_counts().sort_index()
        ax3.bar(team_counts.index, team_counts.values)
        ax3.set_title('Number of Teams per Division')
        ax3.set_xlabel('Division')
        ax3.set_ylabel('Team Count')

        # 4. Win % Distribution by Division
        ax4 = axes[1, 1]
        division_assignments.boxplot(column='Win %', by='Suggested Division', ax=ax4)
        ax4.set_title('Win Percentage Distribution by Division')
        ax4.set_xlabel('Division')
        ax4.set_ylabel('Win %')
        plt.sca(ax4)
        plt.xticks(rotation=0)

        plt.suptitle('Division Balance Analysis', fontsize=16, fontweight='bold', y=0.995)
        plt.tight_layout()
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        print(f"Division visualization saved to {output_file}")
        plt.close()

    def compare_divisions(self, division_assignments):
        """
        Compare current vs suggested divisions if current division data is available

        Args:
            division_assignments: DataFrame with team assignments

        Returns:
            DataFrame showing changes
        """
        if 'Current Division' not in division_assignments.columns:
            print("No current division data available for comparison")
            return None

        changes = division_assignments[
            division_assignments['Current Division'] != division_assignments['Suggested Division']
        ].copy()

        changes = changes[['Team', 'Current Division', 'Suggested Division', 'Strength', 'Win %', 'Points']]

        return changes


def main():
    import glob

    # Find most recent games file
    games_files = glob.glob('output/games_*.csv')
    if not games_files:
        print("No games CSV files found. Run games_scraper.py first.")
        return

    games_file = max(games_files)
    print(f"Loading games data from {games_file}")

    # Find most recent standings file (optional)
    standings_files = glob.glob('output/team_standings_*.csv')
    standings_file = max(standings_files) if standings_files else None
    if standings_file:
        print(f"Loading standings data from {standings_file}")

    # Create analyzer
    analyzer = DivisionAnalyzer(games_file, standings_file)

    print(f"\nTotal games: {len(analyzer.games)}")
    print(f"Completed games: {len(analyzer.completed_games)}")

    # Calculate team metrics
    print("\nCalculating team metrics...")
    team_metrics = analyzer.calculate_team_metrics()

    print("\n" + "="*80)
    print("TEAM PERFORMANCE METRICS (sorted by strength)")
    print("="*80)
    print(team_metrics.to_string(index=False))

    # Suggest divisions
    print("\n" + "="*80)
    print("SUGGESTED DIVISION ASSIGNMENTS (using snake draft for balance)")
    print("="*80)

    division_assignments, division_strengths = analyzer.suggest_divisions(team_metrics, num_divisions=5)

    # Print by division
    for div in sorted(division_assignments['Suggested Division'].unique()):
        div_teams = division_assignments[division_assignments['Suggested Division'] == div]
        print(f"\nDivision {div} (Total Strength: {division_strengths[div]:.1f}):")
        print(div_teams[['Team', 'W', 'L', 'T', 'Win %', 'GD', 'Strength']].to_string(index=False))

    # Compare with current divisions if available
    if 'Current Division' in division_assignments.columns:
        print("\n" + "="*80)
        print("TEAMS THAT WOULD CHANGE DIVISIONS")
        print("="*80)
        changes = analyzer.compare_divisions(division_assignments)
        if changes is not None and len(changes) > 0:
            print(changes.to_string(index=False))
        else:
            print("No changes from current divisions")

    # Create visualization
    Path("output/visualizations").mkdir(parents=True, exist_ok=True)
    analyzer.visualize_divisions(
        division_assignments,
        division_strengths,
        output_file='output/visualizations/division_balance.png'
    )

    # Save suggested divisions to CSV
    output_file = 'output/suggested_divisions.csv'
    division_assignments.to_csv(output_file, index=False)
    print(f"\nSuggested divisions saved to {output_file}")

    # Print balance statistics
    print("\n" + "="*80)
    print("DIVISION BALANCE STATISTICS")
    print("="*80)
    strengths = list(division_strengths.values())
    print(f"Average division strength: {np.mean(strengths):.2f}")
    print(f"Std dev of division strength: {np.std(strengths):.2f}")
    print(f"Range: {min(strengths):.2f} - {max(strengths):.2f}")
    print(f"Balance score (lower is better): {np.std(strengths):.2f}")


if __name__ == "__main__":
    main()
