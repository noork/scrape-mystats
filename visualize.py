import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
import sqlite3


class HockeyStatsVisualizer:
    def __init__(self, data_source):
        """
        Initialize visualizer with data source
        data_source can be:
        - pandas DataFrame
        - path to CSV file
        - path to SQLite database
        """
        self.data = self._load_data(data_source)
        self._clean_data()

    def _load_data(self, source):
        """Load data from various sources"""
        if isinstance(source, pd.DataFrame):
            return source
        elif isinstance(source, str):
            if source.endswith('.csv'):
                return pd.read_csv(source)
            elif source.endswith('.db'):
                conn = sqlite3.connect(source)
                df = pd.read_sql_query("SELECT * FROM player_stats", conn)
                conn.close()
                return df
        raise ValueError("Unsupported data source type")

    def _clean_data(self):
        """Clean and convert numeric columns"""
        # Common numeric columns in hockey stats
        numeric_cols = ['GP', 'G', 'A', 'PTS', 'PIM', 'PIM/GP', 'PPG', 'SHG', 'OTG', 'ENG', 'SOG', 'HT']

        for col in numeric_cols:
            if col in self.data.columns:
                self.data[col] = pd.to_numeric(self.data[col], errors='coerce')

    def _get_column(self, *possible_names):
        """Find a column by trying different name variations (case-insensitive)"""
        for name in possible_names:
            # Try exact match first
            if name in self.data.columns:
                return name
            # Try case-insensitive match
            for col in self.data.columns:
                if col.upper() == name.upper():
                    return col
        return None

    def top_scorers(self, n=10, output_file='top_scorers.png'):
        """Create bar chart of top scorers"""
        if 'PTS' not in self.data.columns:
            print("Points (PTS) column not found")
            return

        # Get player name column (might be 'Player', '#', or combined)
        player_col = self._get_player_column()

        top_players = self.data.nlargest(n, 'PTS')

        plt.figure(figsize=(12, 6))
        plt.barh(top_players[player_col], top_players['PTS'])
        plt.xlabel('Points')
        plt.ylabel('Player')
        plt.title(f'Top {n} Scorers')
        plt.gca().invert_yaxis()
        plt.tight_layout()
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        print(f"Chart saved to {output_file}")
        plt.close()

    def goals_vs_assists(self, output_file='goals_vs_assists.png'):
        """Create scatter plot of goals vs assists"""
        if 'G' not in self.data.columns or 'A' not in self.data.columns:
            print("Goals (G) or Assists (A) column not found")
            return

        plt.figure(figsize=(10, 8))
        plt.scatter(self.data['G'], self.data['A'], alpha=0.6)
        plt.xlabel('Goals')
        plt.ylabel('Assists')
        plt.title('Goals vs Assists')
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        print(f"Chart saved to {output_file}")
        plt.close()

    def team_comparison(self, output_file='team_comparison.png'):
        """Create bar chart comparing team performance"""
        team_col = self._get_column('Team', 'TEAM')
        pts_col = self._get_column('PTS', 'Points')

        if not team_col or not pts_col:
            print("Team or PTS column not found")
            return

        team_stats = self.data.groupby(team_col)[pts_col].sum().sort_values(ascending=False)

        plt.figure(figsize=(12, 6))
        plt.bar(team_stats.index, team_stats.values)
        plt.xlabel('Team')
        plt.ylabel('Total Points')
        plt.title('Team Points Comparison')
        plt.xticks(rotation=45, ha='right')
        plt.tight_layout()
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        print(f"Chart saved to {output_file}")
        plt.close()

    def stats_distribution(self, output_file='stats_distribution.png'):
        """Create histogram showing distribution of key stats"""
        stats_cols = []
        for col in ['G', 'A', 'PTS']:
            if col in self.data.columns:
                stats_cols.append(col)

        if not stats_cols:
            print("No stats columns found for distribution")
            return

        fig, axes = plt.subplots(1, len(stats_cols), figsize=(15, 5))

        if len(stats_cols) == 1:
            axes = [axes]

        for ax, col in zip(axes, stats_cols):
            ax.hist(self.data[col].dropna(), bins=20, edgecolor='black', alpha=0.7)
            ax.set_xlabel(col)
            ax.set_ylabel('Frequency')
            ax.set_title(f'{col} Distribution')
            ax.grid(True, alpha=0.3)

        plt.tight_layout()
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        print(f"Chart saved to {output_file}")
        plt.close()

    def position_analysis(self, output_file='position_analysis.png'):
        """Analyze stats by position"""
        pos_col = self._get_column('POS', 'Position')
        pts_col = self._get_column('PTS', 'Points')

        if not pos_col or not pts_col:
            print("POS or PTS column not found")
            return

        position_stats = self.data.groupby(pos_col)[pts_col].agg(['mean', 'sum', 'count'])

        fig, axes = plt.subplots(1, 2, figsize=(15, 6))

        # Average points by position
        axes[0].bar(position_stats.index, position_stats['mean'])
        axes[0].set_xlabel('Position')
        axes[0].set_ylabel('Average Points')
        axes[0].set_title('Average Points by Position')

        # Total points by position
        axes[1].bar(position_stats.index, position_stats['sum'])
        axes[1].set_xlabel('Position')
        axes[1].set_ylabel('Total Points')
        axes[1].set_title('Total Points by Position')

        plt.tight_layout()
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        print(f"Chart saved to {output_file}")
        plt.close()

    def pim_gp_by_team(self, output_file='pim_gp_by_team.png', min_games=3):
        """
        Create bar chart of average PIM/GP per team for players with more than min_games

        Args:
            output_file: Path to save the visualization
            min_games: Minimum games played to include player (default 3)
        """
        # Clean numeric columns
        gp_col = self._get_column('GP', 'Games Played')
        pim_gp_col = self._get_column('PIM/GP')

        if not gp_col or not pim_gp_col:
            print("GP or PIM/GP column not found")
            return

        # Create working copy
        df = self.data.copy()
        df['GP_numeric'] = pd.to_numeric(df[gp_col], errors='coerce')
        df['PIM_GP_numeric'] = pd.to_numeric(df[pim_gp_col], errors='coerce')

        # Filter players with more than min_games
        filtered_df = df[df['GP_numeric'] > min_games].copy()

        # Find team column - prefer Team Name if available
        team_col = self._get_column('Team Name', 'TEAM', 'Team')

        if not team_col:
            print("No team column found")
            return

        # Calculate average PIM/GP per team
        team_pim_stats = filtered_df.groupby(team_col)['PIM_GP_numeric'].agg(['mean', 'count']).reset_index()
        team_pim_stats.columns = [team_col, 'Avg_PIM_GP', 'Player_Count']

        # Sort by average PIM/GP descending
        team_pim_stats = team_pim_stats.sort_values('Avg_PIM_GP', ascending=False)

        # Remove teams with NaN names
        team_pim_stats = team_pim_stats.dropna(subset=[team_col])

        # Create visualization
        fig, ax = plt.subplots(figsize=(14, 8))

        bars = ax.barh(team_pim_stats[team_col], team_pim_stats['Avg_PIM_GP'])

        # Color bars based on PIM/GP level
        colors = ['#d73027' if x > 0.5 else '#fee08b' if x > 0.2 else '#1a9850'
                  for x in team_pim_stats['Avg_PIM_GP']]
        for bar, color in zip(bars, colors):
            bar.set_color(color)

        ax.set_xlabel('Average PIM/GP', fontsize=12)
        ax.set_ylabel('Team', fontsize=12)
        ax.set_title(f'Average Penalties per Game by Team\n(Players with > {min_games} games)',
                     fontsize=14, fontweight='bold')
        ax.grid(axis='x', alpha=0.3)

        # Add value labels on bars
        for i, (idx, row) in enumerate(team_pim_stats.iterrows()):
            ax.text(row['Avg_PIM_GP'] + 0.01, i,
                    f"{row['Avg_PIM_GP']:.2f} ({int(row['Player_Count'])} players)",
                    va='center', fontsize=9)

        # Invert y-axis so highest is on top
        ax.invert_yaxis()

        plt.tight_layout()
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        print(f"Chart saved to {output_file}")
        plt.close()

    def pim_gp_by_player(self, output_file='pim_gp_by_player.png', min_games=3, top_n=100):
        """
        Create bar chart of PIM/GP by player for players with more than min_games

        Args:
            output_file: Path to save the visualization
            min_games: Minimum games played to include player (default 3)
            top_n: Number of top players to show (default 20)
        """
        # Clean numeric columns
        gp_col = self._get_column('GP', 'Games Played')
        pim_gp_col = self._get_column('PIM/GP')
        player_col = self._get_column('PLAYERS', 'Player', 'Name', '#')

        if not gp_col or not pim_gp_col or not player_col:
            print("Required columns not found")
            return

        # Create working copy
        df = self.data.copy()
        df['GP_numeric'] = pd.to_numeric(df[gp_col], errors='coerce')
        df['PIM_GP_numeric'] = pd.to_numeric(df[pim_gp_col], errors='coerce')

        # Filter players with more than min_games
        filtered_df = df[df['GP_numeric'] > min_games].copy()

        # Sort by PIM/GP descending and take top N
        top_players = filtered_df.nlargest(top_n, 'PIM_GP_numeric')

        # Get team column for additional info
        team_col = self._get_column('Team Name', 'TEAM', 'Team')

        # Create visualization with dynamic height based on number of players
        fig_height = max(20, len(top_players) * 0.4)  # At least 20 inches tall
        fig, ax = plt.subplots(figsize=(14, fig_height))

        bars = ax.barh(range(len(top_players)), top_players['PIM_GP_numeric'])

        # Color bars based on PIM/GP level
        colors = ['#d73027' if x > 1.0 else '#fc8d59' if x > 0.5 else '#fee08b' if x > 0.2 else '#1a9850'
                  for x in top_players['PIM_GP_numeric']]
        for bar, color in zip(bars, colors):
            bar.set_color(color)

        # Set player names as y-tick labels
        player_labels = []
        for idx, row in top_players.iterrows():
            player_name = str(row[player_col])
            if team_col and pd.notna(row[team_col]):
                player_labels.append(f"{player_name} ({row[team_col]})")
            else:
                player_labels.append(player_name)

        ax.set_yticks(range(len(top_players)))
        ax.set_yticklabels(player_labels, fontsize=7)

        ax.set_xlabel('PIM/GP', fontsize=12)
        ax.set_ylabel('Player', fontsize=12)
        ax.set_title(f'Top {top_n} Players by Penalties per Game\n(Players with > {min_games} games)',
                     fontsize=14, fontweight='bold')
        ax.grid(axis='x', alpha=0.3)

        # Add value labels on bars
        for i, (idx, row) in enumerate(top_players.iterrows()):
            ax.text(row['PIM_GP_numeric'] + 0.02, i,
                    f"{row['PIM_GP_numeric']:.2f} ({int(row['GP_numeric'])} GP)",
                    va='center', fontsize=8)

        # Invert y-axis so highest is on top
        ax.invert_yaxis()

        plt.tight_layout()
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        print(f"Chart saved to {output_file}")
        plt.close()

    def p_gp_by_team(self, output_file='p_gp_by_team.png', min_games=3):
        """
        Create bar chart of average P/GP per team for players with more than min_games

        Args:
            output_file: Path to save the visualization
            min_games: Minimum games played to include player (default 3)
        """
        # Clean numeric columns
        gp_col = self._get_column('GP', 'Games Played')
        p_gp_col = self._get_column('P/GP', 'Points/GP')

        if not gp_col or not p_gp_col:
            print("GP or P/GP column not found")
            return

        # Create working copy
        df = self.data.copy()
        df['GP_numeric'] = pd.to_numeric(df[gp_col], errors='coerce')
        df['P_GP_numeric'] = pd.to_numeric(df[p_gp_col], errors='coerce')

        # Filter players with more than min_games
        filtered_df = df[df['GP_numeric'] > min_games].copy()

        # Find team column - prefer Team Name if available
        team_col = self._get_column('Team Name', 'TEAM', 'Team')

        if not team_col:
            print("No team column found")
            return

        # Calculate average P/GP per team
        team_stats = filtered_df.groupby(team_col)['P_GP_numeric'].agg(['mean', 'count']).reset_index()
        team_stats.columns = [team_col, 'Avg_P_GP', 'Player_Count']

        # Sort by average P/GP descending
        team_stats = team_stats.sort_values('Avg_P_GP', ascending=False)

        # Remove teams with NaN names
        team_stats = team_stats.dropna(subset=[team_col])

        # Create visualization
        fig, ax = plt.subplots(figsize=(14, 8))

        bars = ax.barh(team_stats[team_col], team_stats['Avg_P_GP'])

        # Color bars based on P/GP level (green for high scoring)
        colors = ['#1a9850' if x > 1.0 else '#91cf60' if x > 0.7 else '#fee08b' if x > 0.4 else '#d73027'
                  for x in team_stats['Avg_P_GP']]
        for bar, color in zip(bars, colors):
            bar.set_color(color)

        ax.set_xlabel('Average P/GP', fontsize=12)
        ax.set_ylabel('Team', fontsize=12)
        ax.set_title(f'Average Points per Game by Team\n(Players with > {min_games} games)',
                     fontsize=14, fontweight='bold')
        ax.grid(axis='x', alpha=0.3)

        # Add value labels on bars
        for i, (idx, row) in enumerate(team_stats.iterrows()):
            ax.text(row['Avg_P_GP'] + 0.01, i,
                    f"{row['Avg_P_GP']:.2f} ({int(row['Player_Count'])} players)",
                    va='center', fontsize=9)

        # Invert y-axis so highest is on top
        ax.invert_yaxis()

        plt.tight_layout()
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        print(f"Chart saved to {output_file}")
        plt.close()

    def p_gp_by_player(self, output_file='p_gp_by_player.png', min_games=3, top_n=100):
        """
        Create bar chart of P/GP by player for players with more than min_games

        Args:
            output_file: Path to save the visualization
            min_games: Minimum games played to include player (default 3)
            top_n: Number of top players to show (default 100)
        """
        # Clean numeric columns
        gp_col = self._get_column('GP', 'Games Played')
        p_gp_col = self._get_column('P/GP', 'Points/GP')
        player_col = self._get_column('PLAYERS', 'Player', 'Name', '#')

        if not gp_col or not p_gp_col or not player_col:
            print("Required columns not found")
            return

        # Create working copy
        df = self.data.copy()
        df['GP_numeric'] = pd.to_numeric(df[gp_col], errors='coerce')
        df['P_GP_numeric'] = pd.to_numeric(df[p_gp_col], errors='coerce')

        # Filter players with more than min_games
        filtered_df = df[df['GP_numeric'] > min_games].copy()

        # Sort by P/GP descending and take top N
        top_players = filtered_df.nlargest(top_n, 'P_GP_numeric')

        # Get team column for additional info
        team_col = self._get_column('Team Name', 'TEAM', 'Team')

        # Create visualization with dynamic height based on number of players
        fig_height = max(20, len(top_players) * 0.4)  # At least 20 inches tall
        fig, ax = plt.subplots(figsize=(14, fig_height))

        bars = ax.barh(range(len(top_players)), top_players['P_GP_numeric'])

        # Color bars based on P/GP level (green for high scoring)
        colors = ['#1a9850' if x > 1.5 else '#91cf60' if x > 1.0 else '#fee08b' if x > 0.7 else '#fc8d59'
                  for x in top_players['P_GP_numeric']]
        for bar, color in zip(bars, colors):
            bar.set_color(color)

        # Set player names as y-tick labels
        player_labels = []
        for idx, row in top_players.iterrows():
            player_name = str(row[player_col])
            if team_col and pd.notna(row[team_col]):
                player_labels.append(f"{player_name} ({row[team_col]})")
            else:
                player_labels.append(player_name)

        ax.set_yticks(range(len(top_players)))
        ax.set_yticklabels(player_labels, fontsize=7)

        ax.set_xlabel('P/GP', fontsize=12)
        ax.set_ylabel('Player', fontsize=12)
        ax.set_title(f'Top {top_n} Players by Points per Game\n(Players with > {min_games} games)',
                     fontsize=14, fontweight='bold')
        ax.grid(axis='x', alpha=0.3)

        # Add value labels on bars
        for i, (idx, row) in enumerate(top_players.iterrows()):
            ax.text(row['P_GP_numeric'] + 0.02, i,
                    f"{row['P_GP_numeric']:.2f} ({int(row['GP_numeric'])} GP)",
                    va='center', fontsize=8)

        # Invert y-axis so highest is on top
        ax.invert_yaxis()

        plt.tight_layout()
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        print(f"Chart saved to {output_file}")
        plt.close()

    def g_gp_by_team(self, output_file='g_gp_by_team.png', min_games=3):
        """
        Create bar chart of average G/GP per team for players with more than min_games

        Args:
            output_file: Path to save the visualization
            min_games: Minimum games played to include player (default 3)
        """
        # Clean numeric columns
        gp_col = self._get_column('GP', 'Games Played')
        g_gp_col = self._get_column('G/GP', 'Goals/GP')

        if not gp_col or not g_gp_col:
            print("GP or G/GP column not found")
            return

        # Create working copy
        df = self.data.copy()
        df['GP_numeric'] = pd.to_numeric(df[gp_col], errors='coerce')
        df['G_GP_numeric'] = pd.to_numeric(df[g_gp_col], errors='coerce')

        # Filter players with more than min_games
        filtered_df = df[df['GP_numeric'] > min_games].copy()

        # Find team column - prefer Team Name if available
        team_col = self._get_column('Team Name', 'TEAM', 'Team')

        if not team_col:
            print("No team column found")
            return

        # Calculate average G/GP per team
        team_stats = filtered_df.groupby(team_col)['G_GP_numeric'].agg(['mean', 'count']).reset_index()
        team_stats.columns = [team_col, 'Avg_G_GP', 'Player_Count']

        # Sort by average G/GP descending
        team_stats = team_stats.sort_values('Avg_G_GP', ascending=False)

        # Remove teams with NaN names
        team_stats = team_stats.dropna(subset=[team_col])

        # Create visualization
        fig, ax = plt.subplots(figsize=(14, 8))

        bars = ax.barh(team_stats[team_col], team_stats['Avg_G_GP'])

        # Color bars based on G/GP level (green for high scoring)
        colors = ['#1a9850' if x > 0.6 else '#91cf60' if x > 0.4 else '#fee08b' if x > 0.2 else '#d73027'
                  for x in team_stats['Avg_G_GP']]
        for bar, color in zip(bars, colors):
            bar.set_color(color)

        ax.set_xlabel('Average G/GP', fontsize=12)
        ax.set_ylabel('Team', fontsize=12)
        ax.set_title(f'Average Goals per Game by Team\n(Players with > {min_games} games)',
                     fontsize=14, fontweight='bold')
        ax.grid(axis='x', alpha=0.3)

        # Add value labels on bars
        for i, (idx, row) in enumerate(team_stats.iterrows()):
            ax.text(row['Avg_G_GP'] + 0.005, i,
                    f"{row['Avg_G_GP']:.2f} ({int(row['Player_Count'])} players)",
                    va='center', fontsize=9)

        # Invert y-axis so highest is on top
        ax.invert_yaxis()

        plt.tight_layout()
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        print(f"Chart saved to {output_file}")
        plt.close()

    def g_gp_by_player(self, output_file='g_gp_by_player.png', min_games=3, top_n=100):
        """
        Create bar chart of G/GP by player for players with more than min_games

        Args:
            output_file: Path to save the visualization
            min_games: Minimum games played to include player (default 3)
            top_n: Number of top players to show (default 100)
        """
        # Clean numeric columns
        gp_col = self._get_column('GP', 'Games Played')
        g_gp_col = self._get_column('G/GP', 'Goals/GP')
        player_col = self._get_column('PLAYERS', 'Player', 'Name', '#')

        if not gp_col or not g_gp_col or not player_col:
            print("Required columns not found")
            return

        # Create working copy
        df = self.data.copy()
        df['GP_numeric'] = pd.to_numeric(df[gp_col], errors='coerce')
        df['G_GP_numeric'] = pd.to_numeric(df[g_gp_col], errors='coerce')

        # Filter players with more than min_games
        filtered_df = df[df['GP_numeric'] > min_games].copy()

        # Sort by G/GP descending and take top N
        top_players = filtered_df.nlargest(top_n, 'G_GP_numeric')

        # Get team column for additional info
        team_col = self._get_column('Team Name', 'TEAM', 'Team')

        # Create visualization with dynamic height based on number of players
        fig_height = max(20, len(top_players) * 0.4)  # At least 20 inches tall
        fig, ax = plt.subplots(figsize=(14, fig_height))

        bars = ax.barh(range(len(top_players)), top_players['G_GP_numeric'])

        # Color bars based on G/GP level (green for high scoring)
        colors = ['#1a9850' if x > 1.0 else '#91cf60' if x > 0.6 else '#fee08b' if x > 0.4 else '#fc8d59'
                  for x in top_players['G_GP_numeric']]
        for bar, color in zip(bars, colors):
            bar.set_color(color)

        # Set player names as y-tick labels
        player_labels = []
        for idx, row in top_players.iterrows():
            player_name = str(row[player_col])
            if team_col and pd.notna(row[team_col]):
                player_labels.append(f"{player_name} ({row[team_col]})")
            else:
                player_labels.append(player_name)

        ax.set_yticks(range(len(top_players)))
        ax.set_yticklabels(player_labels, fontsize=7)

        ax.set_xlabel('G/GP', fontsize=12)
        ax.set_ylabel('Player', fontsize=12)
        ax.set_title(f'Top {top_n} Players by Goals per Game\n(Players with > {min_games} games)',
                     fontsize=14, fontweight='bold')
        ax.grid(axis='x', alpha=0.3)

        # Add value labels on bars
        for i, (idx, row) in enumerate(top_players.iterrows()):
            ax.text(row['G_GP_numeric'] + 0.01, i,
                    f"{row['G_GP_numeric']:.2f} ({int(row['GP_numeric'])} GP)",
                    va='center', fontsize=8)

        # Invert y-axis so highest is on top
        ax.invert_yaxis()

        plt.tight_layout()
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        print(f"Chart saved to {output_file}")
        plt.close()

    def _get_player_column(self):
        """Find the column containing player names"""
        for col in ['Player', 'Name', '#']:
            if col in self.data.columns:
                return col
        return self.data.columns[0]

    def create_dashboard(self, output_dir='output/visualizations'):
        """Create all visualizations"""
        Path(output_dir).mkdir(parents=True, exist_ok=True)

        print(f"Creating visualizations in {output_dir}/...")
        print("="*50)

        self.top_scorers(output_file=f'{output_dir}/top_scorers.png')
        self.goals_vs_assists(output_file=f'{output_dir}/goals_vs_assists.png')
        self.team_comparison(output_file=f'{output_dir}/team_comparison.png')
        self.stats_distribution(output_file=f'{output_dir}/stats_distribution.png')
        self.position_analysis(output_file=f'{output_dir}/position_analysis.png')
        self.pim_gp_by_team(output_file=f'{output_dir}/pim_gp_by_team.png')
        self.pim_gp_by_player(output_file=f'{output_dir}/pim_gp_by_player.png')
        self.p_gp_by_team(output_file=f'{output_dir}/p_gp_by_team.png')
        self.p_gp_by_player(output_file=f'{output_dir}/p_gp_by_player.png')
        self.g_gp_by_team(output_file=f'{output_dir}/g_gp_by_team.png')
        self.g_gp_by_player(output_file=f'{output_dir}/g_gp_by_player.png')

        print("="*50)
        print(f"All visualizations saved to {output_dir}/")


class GamesVisualizer:
    def __init__(self, data_source):
        """
        Initialize visualizer with games data source
        data_source can be:
        - pandas DataFrame
        - path to CSV file
        """
        self.data = self._load_data(data_source)
        self._clean_data()

    def _load_data(self, source):
        """Load data from various sources"""
        if isinstance(source, pd.DataFrame):
            return source
        elif isinstance(source, str):
            if source.endswith('.csv'):
                return pd.read_csv(source)
        raise ValueError("Unsupported data source type")

    def _clean_data(self):
        """Clean and convert numeric columns"""
        # Convert score columns to numeric
        if 'Away Score' in self.data.columns:
            self.data['Away Score'] = pd.to_numeric(self.data['Away Score'], errors='coerce')
        if 'Home Score' in self.data.columns:
            self.data['Home Score'] = pd.to_numeric(self.data['Home Score'], errors='coerce')

        # Calculate score differential
        if 'Away Score' in self.data.columns and 'Home Score' in self.data.columns:
            self.data['Score Differential'] = abs(self.data['Away Score'] - self.data['Home Score'])
            self.data['Total Score'] = self.data['Away Score'] + self.data['Home Score']

    def closest_games(self, output_file='closest_games.png', top_n=30):
        """
        Visualize the closest games (smallest score differentials)

        Args:
            output_file: Path to save the visualization
            top_n: Number of closest games to show (default 30)
        """
        # Filter for completed games (those with valid scores)
        completed_games = self.data.dropna(subset=['Away Score', 'Home Score']).copy()

        if len(completed_games) == 0:
            print("No completed games found")
            return

        # Sort by score differential and take the closest games
        closest = completed_games.nsmallest(top_n, 'Score Differential', keep='all')
        closest = closest.sort_values('Score Differential', ascending=True).head(top_n)

        # Create game labels
        game_labels = []
        for idx, row in closest.iterrows():
            away_team = row.get('Away Team Name', row.get('Away Team', 'Unknown'))
            home_team = row.get('Home Team Name', row.get('Home Team', 'Unknown'))
            away_score = int(row['Away Score'])
            home_score = int(row['Home Score'])
            diff = int(row['Score Differential'])

            # Determine winner/tie
            if away_score > home_score:
                label = f"{away_team} {away_score} vs {home_team} {home_score}"
            elif home_score > away_score:
                label = f"{home_team} {home_score} vs {away_team} {away_score}"
            else:
                label = f"{away_team} {away_score} vs {home_team} {home_score} (TIE)"

            game_labels.append(label)

        # Create visualization
        fig_height = max(12, len(closest) * 0.5)
        fig, ax = plt.subplots(figsize=(16, fig_height))

        bars = ax.barh(range(len(closest)), closest['Score Differential'])

        # Color bars based on differential
        colors = ['#1a9850' if x == 0 else '#91cf60' if x == 1 else '#fee08b' if x == 2 else '#fc8d59'
                  for x in closest['Score Differential']]
        for bar, color in zip(bars, colors):
            bar.set_color(color)

        # Set game labels as y-tick labels
        ax.set_yticks(range(len(closest)))
        ax.set_yticklabels(game_labels, fontsize=9)

        ax.set_xlabel('Score Differential', fontsize=12)
        ax.set_ylabel('Matchup', fontsize=12)
        ax.set_title(f'Top {top_n} Closest Games by Score Differential', fontsize=14, fontweight='bold')
        ax.grid(axis='x', alpha=0.3)

        # Add value labels on bars
        for i, (idx, row) in enumerate(closest.iterrows()):
            diff = int(row['Score Differential'])
            date = row.get('Date', 'N/A')
            ax.text(row['Score Differential'] + 0.05, i,
                    f"Diff: {diff} | {date}",
                    va='center', fontsize=8)

        # Invert y-axis so closest games are on top
        ax.invert_yaxis()

        plt.tight_layout()
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        print(f"Chart saved to {output_file}")
        plt.close()

        return closest


def main():
    # Example usage - visualize from the most recent CSV file
    import glob

    csv_files = glob.glob('output/hockey_stats_*.csv')

    if not csv_files:
        print("No CSV files found. Run scraper.py first.")
        return

    # Use the most recent file
    latest_file = max(csv_files)
    print(f"Loading data from {latest_file}")

    viz = HockeyStatsVisualizer(latest_file)
    viz.create_dashboard()


if __name__ == "__main__":
    main()
