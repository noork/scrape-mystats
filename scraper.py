import requests
from bs4 import BeautifulSoup
import pandas as pd
import json
import sqlite3
from datetime import datetime
from pathlib import Path


class HockeyStatsScraper:
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

    def parse_table(self, html_content):
        """Parse the HTML table and extract player stats"""
        soup = BeautifulSoup(html_content, 'html.parser')

        # Find the stats table - look for table with class or id containing 'stats' or 'dataTable'
        table = soup.find('table', {'id': lambda x: x and ('stats' in x.lower() or 'datatable' in x.lower())})

        if not table:
            # Try finding by class
            table = soup.find('table', {'class': lambda x: x and any('stats' in str(c).lower() or 'datatable' in str(c).lower() for c in (x if isinstance(x, list) else [x]))})

        if not table:
            # Last resort: find all tables and pick the largest one
            tables = soup.find_all('table')
            if tables:
                table = max(tables, key=lambda t: len(t.find_all('tr')))
            else:
                raise ValueError("No table found on the page")

        # Extract headers
        headers = []
        header_row = table.find('thead').find('tr') if table.find('thead') else table.find('tr')

        for th in header_row.find_all(['th', 'td']):
            header_text = th.get_text(strip=True)
            # Handle empty or duplicate headers
            if not header_text:
                header_text = f"Column_{len(headers)}"
            # Make headers unique
            original_header = header_text
            counter = 1
            while header_text in headers:
                header_text = f"{original_header}_{counter}"
                counter += 1
            headers.append(header_text)

        # Extract data rows
        rows_data = []
        tbody = table.find('tbody') if table.find('tbody') else table

        for row in tbody.find_all('tr'):
            # Skip header rows in tbody
            if row.find('th'):
                continue

            cells = row.find_all(['td', 'th'])
            if not cells:
                continue

            row_data = [cell.get_text(strip=True) for cell in cells]

            # Only add rows with data
            if row_data and any(cell for cell in row_data):
                # Pad or trim row to match header length
                if len(row_data) < len(headers):
                    row_data.extend([''] * (len(headers) - len(row_data)))
                elif len(row_data) > len(headers):
                    row_data = row_data[:len(headers)]
                rows_data.append(row_data)

        # Create DataFrame
        df = pd.DataFrame(rows_data, columns=headers)

        print(f"Successfully extracted {len(df)} player records")
        return df

    def scrape(self):
        """Main scraping method"""
        html = self.fetch_page()
        self.data = self.parse_table(html)
        self._add_calculated_columns()
        return self.data

    def _add_calculated_columns(self):
        """Add calculated columns like PIM/GP, Team Name, and Player Name"""
        if self.data is None:
            return

        # Find PIM and GP columns (case-insensitive)
        pim_col = None
        gp_col = None
        team_col = None
        player_col = None

        for col in self.data.columns:
            if col.upper() == 'PIM':
                pim_col = col
            elif col.upper() == 'GP':
                gp_col = col
            elif col.upper() == 'TEAM':
                team_col = col
            elif col.upper() == 'PLAYERS':
                player_col = col

        # Calculate PIM/GP if both columns exist
        if pim_col and gp_col:
            # Convert to numeric
            pim_numeric = pd.to_numeric(self.data[pim_col], errors='coerce')
            gp_numeric = pd.to_numeric(self.data[gp_col], errors='coerce')

            # Calculate PIM/GP, avoiding division by zero
            self.data['PIM/GP'] = (pim_numeric / gp_numeric).round(2)
            self.data['PIM/GP'] = self.data['PIM/GP'].fillna(0)

            print("Added calculated column: PIM/GP")

        # Add team full names if mapping exists
        if team_col and self.team_mapping:
            # Map abbreviations to full names, keep abbreviation if not found
            self.data['Team Name'] = self.data[team_col].map(self.team_mapping)

            # Count how many teams were successfully mapped
            mapped_count = self.data['Team Name'].notna().sum()
            total_count = len(self.data)

            print(f"Added Team Name column: {mapped_count}/{total_count} teams mapped")

        # Add reformatted player names (first_name last_name)
        if player_col:
            self.data['PLAYER NAME'] = self.data[player_col].apply(self._reformat_player_name)
            print("Added PLAYER NAME column with reformatted names")

    def _reformat_player_name(self, player_string):
        """
        Reformat player name from 'last_name, first_name #number' to 'first_name last_name'

        Args:
            player_string: Original player string (e.g., 'Smith, John #42')

        Returns:
            Reformatted name (e.g., 'John Smith')
        """
        if pd.isna(player_string) or not player_string:
            return ''

        # Remove any leading/trailing whitespace
        player_string = str(player_string).strip()

        # Remove the # and everything after it
        if '#' in player_string:
            player_string = player_string.split('#')[0].strip()

        # Split by comma
        if ',' in player_string:
            parts = player_string.split(',')
            last_name = parts[0].strip()
            first_name = parts[1].strip() if len(parts) > 1 else ''

            # Return as "first_name last_name"
            if first_name and last_name:
                return f"{first_name} {last_name}"
            elif last_name:
                return last_name
            else:
                return ''
        else:
            # If no comma, return as-is
            return player_string

    def export_to_csv(self, filename=None):
        """Export data to CSV file"""
        if self.data is None:
            raise ValueError("No data to export. Run scrape() first.")

        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"output/hockey_stats_{timestamp}.csv"

        # Ensure output directory exists
        Path("output").mkdir(exist_ok=True)

        self.data.to_csv(filename, index=False)
        print(f"Data exported to {filename}")
        return filename

    def export_to_json(self, filename=None):
        """Export data to JSON file"""
        if self.data is None:
            raise ValueError("No data to export. Run scrape() first.")

        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"output/hockey_stats_{timestamp}.json"

        # Ensure output directory exists
        Path("output").mkdir(exist_ok=True)

        self.data.to_json(filename, orient='records', indent=2)
        print(f"Data exported to {filename}")
        return filename

    def save_to_database(self, db_name="output/hockey_stats.db", table_name="player_stats"):
        """Save data to SQLite database"""
        if self.data is None:
            raise ValueError("No data to save. Run scrape() first.")

        conn = sqlite3.connect(db_name)

        # Add timestamp column
        data_with_timestamp = self.data.copy()
        data_with_timestamp['scraped_at'] = datetime.now().isoformat()

        # Save to database
        data_with_timestamp.to_sql(table_name, conn, if_exists='append', index=False)

        print(f"Data saved to database {db_name}, table {table_name}")
        print(f"Total records in database: {self._get_record_count(conn, table_name)}")

        conn.close()
        return db_name

    def _get_record_count(self, conn, table_name):
        """Get the total number of records in the database"""
        cursor = conn.cursor()
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        count = cursor.fetchone()[0]
        return count


def main():
    # URL to scrape
    url = "https://www.mystatsonline.com/hockey/visitor/league/stats/skater_hockey.aspx?IDLeague=6894"

    # Create scraper instance
    scraper = HockeyStatsScraper(url)

    # Scrape the data
    data = scraper.scrape()

    # Display preview
    print("\n" + "="*50)
    print("DATA PREVIEW")
    print("="*50)
    print(data.head())
    print(f"\nTotal columns: {len(data.columns)}")
    print(f"Columns: {', '.join(data.columns.tolist())}")

    # Export to CSV
    print("\n" + "="*50)
    csv_file = scraper.export_to_csv()

    # Export to JSON
    json_file = scraper.export_to_json()

    # Save to database
    print("\n" + "="*50)
    db_file = scraper.save_to_database()

    print("\n" + "="*50)
    print("SCRAPING COMPLETE!")
    print("="*50)


if __name__ == "__main__":
    main()
