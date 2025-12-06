import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
from pathlib import Path
import re


class GamesScraper:
    def __init__(self, url, team_mapping_file='team_mapping.csv'):
        self.url = url
        self.data = None
        self.team_mapping = self._load_team_mapping(team_mapping_file)

    def _load_team_mapping(self, mapping_file):
        """Load team abbreviation to full name mapping"""
        try:
            mapping_df = pd.read_csv(mapping_file)
            # Create dictionary mapping abbreviation to team name
            mapping = dict(zip(mapping_df['Abbreviation'], mapping_df['Team']))
            print(f"Loaded {len(mapping)} team mappings")
            return mapping
        except FileNotFoundError:
            print(f"Team mapping file not found, skipping team name mapping")
            return {}
        except Exception as e:
            print(f"Error loading team mapping: {e}, skipping team name mapping")
            return {}

    def fetch_page(self):
        """Fetch the HTML content from the URL"""
        print(f"Fetching data from {self.url}...")
        response = requests.get(self.url)
        response.raise_for_status()
        return response.text

    def parse_games(self, html_content):
        """Parse the HTML table and extract game information"""
        soup = BeautifulSoup(html_content, 'html.parser')

        # Find the games table by ID
        table = soup.find('table', {'id': 'maincontent_gvGameList'})

        if not table:
            # Fallback: find table with datatable class
            table = soup.find('table', {'class': lambda x: x and 'datatable' in ' '.join(x).lower()})

        if not table:
            raise ValueError("No games table found on the page")

        # Extract all rows
        all_rows = table.find_all('tr')

        # Extract data rows
        all_games = []
        current_date = None

        for row in all_rows[1:]:  # Skip header row
            cells = row.find_all(['td', 'th'])

            # Check if this is a date header row (only 1 cell)
            if len(cells) == 1:
                current_date = cells[0].get_text(strip=True)
                continue

            # Game rows should have 8 cells
            if len(cells) != 8:
                continue

            # Extract game information
            # Cell 0: Date/Time (Game ID and time)
            # Cell 1: Away team name
            # Cell 2: Away team score
            # Cell 3: Empty separator
            # Cell 4: Home team score
            # Cell 5: Home team name
            # Cell 6: Location
            # Cell 7: Status

            game_time = cells[0].get_text(strip=True)

            # Get away team (from link if available)
            away_team_link = cells[1].find('a')
            away_team = away_team_link.get_text(strip=True) if away_team_link else cells[1].get_text(strip=True)

            away_score = cells[2].get_text(strip=True)

            # Get home team (from link if available)
            home_team_link = cells[5].find('a')
            home_team = home_team_link.get_text(strip=True) if home_team_link else cells[5].get_text(strip=True)

            home_score = cells[4].get_text(strip=True)

            location = cells[6].get_text(strip=True)
            status = cells[7].get_text(strip=True)

            game_dict = {
                'Date': current_date if current_date else '',
                'Game Time': game_time,
                'Away Team': away_team,
                'Away Score': away_score,
                'Home Team': home_team,
                'Home Score': home_score,
                'Location': location,
                'Status': status
            }

            all_games.append(game_dict)

        if not all_games:
            raise ValueError("No game data found on the page")

        # Create DataFrame
        df = pd.DataFrame(all_games)

        print(f"Successfully extracted {len(df)} game records")
        return df

    def scrape(self):
        """Main scraping method"""
        html = self.fetch_page()
        self.data = self.parse_games(html)
        self._add_team_names()
        return self.data

    def _add_team_names(self):
        """Add full team names based on mapping and extract team abbreviations"""
        if self.data is None:
            return

        # Column names are 'Away Team' and 'Home Team'
        away_col = 'Away Team'
        home_col = 'Home Team'

        if away_col in self.data.columns and home_col in self.data.columns and self.team_mapping:
            # Function to split team abbreviation and name
            def split_team_name(team_str):
                """Split concatenated team abbreviation and name"""
                if pd.isna(team_str) or not team_str:
                    return '', ''

                team_str = str(team_str).strip()

                # Try to find the abbreviation in our mapping
                for abbrev in self.team_mapping.keys():
                    if team_str.startswith(abbrev):
                        full_name = team_str[len(abbrev):]
                        return abbrev, full_name

                # If no match found, try to split by detecting capital letter pattern
                match = re.match(r'^([A-Z]{2,4})(.+)$', team_str)
                if match:
                    return match.group(1), match.group(2)

                return team_str, team_str

            # Process away team
            self.data[['Away Team Abbrev', 'Away Team Name Extracted']] = self.data[away_col].apply(
                lambda x: pd.Series(split_team_name(x))
            )

            # Process home team
            self.data[['Home Team Abbrev', 'Home Team Name Extracted']] = self.data[home_col].apply(
                lambda x: pd.Series(split_team_name(x))
            )

            # Map abbreviations to full names from mapping file
            self.data['Away Team Name'] = self.data['Away Team Abbrev'].map(self.team_mapping).fillna(
                self.data['Away Team Name Extracted']
            )
            self.data['Home Team Name'] = self.data['Home Team Abbrev'].map(self.team_mapping).fillna(
                self.data['Home Team Name Extracted']
            )

            # Drop temporary columns
            self.data.drop(['Away Team Name Extracted', 'Home Team Name Extracted'], axis=1, inplace=True)

            # Count mapped teams
            away_mapped = self.data['Away Team Abbrev'].map(self.team_mapping).notna().sum()
            home_mapped = self.data['Home Team Abbrev'].map(self.team_mapping).notna().sum()
            print(f"Added team name columns: {away_mapped + home_mapped}/{len(self.data) * 2} team instances mapped")

    def export_to_csv(self, filename=None):
        """Export data to CSV file"""
        if self.data is None:
            raise ValueError("No data to export. Run scrape() first.")

        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"output/games_{timestamp}.csv"

        # Ensure output directory exists
        Path("output").mkdir(exist_ok=True)

        self.data.to_csv(filename, index=False)
        print(f"Games data exported to {filename}")
        return filename


def main():
    # URL to scrape
    url = "https://www.mystatsonline.com/hockey/visitor/league/schedule_scores/schedule.aspx?IDLeague=6894"

    # Create scraper instance
    scraper = GamesScraper(url)

    # Scrape the data
    data = scraper.scrape()

    # Display preview
    print("\n" + "="*50)
    print("GAMES DATA PREVIEW")
    print("="*50)
    print(data.head(10))
    print(f"\nTotal columns: {len(data.columns)}")
    print(f"Columns: {', '.join(data.columns.tolist())}")

    # Export to CSV
    print("\n" + "="*50)
    csv_file = scraper.export_to_csv()

    print("\n" + "="*50)
    print("GAMES SCRAPING COMPLETE!")
    print("="*50)


if __name__ == "__main__":
    main()
