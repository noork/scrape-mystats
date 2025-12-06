import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
from pathlib import Path


class TeamStandingsScraper:
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

    def parse_standings(self, html_content):
        """Parse the HTML tables and extract team standings"""
        soup = BeautifulSoup(html_content, 'html.parser')

        # Find all tables with standings data (look for tables with class or id containing standings/stats)
        tables = soup.find_all('table', {'id': lambda x: x and ('standings' in x.lower() or 'datatable' in x.lower())})

        if not tables:
            # Fallback: find all tables and filter by size
            all_tables = soup.find_all('table')
            tables = [t for t in all_tables if len(t.find_all('tr')) > 3]

        all_teams = []

        # Divisions are in order: A, B, C, D, NEWBIE
        # This corresponds to the order of tables on the page
        division_names = ['A', 'B', 'C', 'D', 'NEWBIE']

        for table_idx, table in enumerate(tables):
            # Assign division based on table order
            division = division_names[table_idx] if table_idx < len(division_names) else "Unknown"

            # Extract table headers
            headers = []
            header_row = table.find('thead')
            if header_row:
                header_row = header_row.find('tr')
            else:
                # Find first row
                header_row = table.find('tr')

            if not header_row:
                continue

            for th in header_row.find_all(['th', 'td']):
                header_text = th.get_text(strip=True)
                # Skip empty or social media headers
                if not header_text or 'share' in header_text.lower() or 'tweet' in header_text.lower():
                    continue
                # Make headers unique
                original_header = header_text
                counter = 1
                while header_text in headers:
                    header_text = f"{original_header}_{counter}"
                    counter += 1
                headers.append(header_text)

            if not headers:
                continue

            # Extract data rows
            tbody = table.find('tbody') if table.find('tbody') else table

            for row in tbody.find_all('tr'):
                # Skip header rows or rows with th elements
                if row.find('th') or not row.find('td'):
                    continue

                cells = row.find_all('td')
                if not cells:
                    continue

                row_data = []
                for i, cell in enumerate(cells):
                    # Skip social media cells
                    cell_text = cell.get_text(strip=True)
                    if i == 0 and ('share' in cell_text.lower() or not cell_text):
                        continue

                    # Try to get text from links first, otherwise get cell text
                    link = cell.find('a')
                    if link:
                        cell_text = link.get_text(strip=True)
                    else:
                        cell_text = cell.get_text(strip=True)
                    row_data.append(cell_text)

                # Only add rows with substantial data
                if row_data and len([d for d in row_data if d]) >= 5:
                    # Pad or trim row to match header length
                    if len(row_data) < len(headers):
                        row_data.extend([''] * (len(headers) - len(row_data)))
                    elif len(row_data) > len(headers):
                        row_data = row_data[:len(headers)]

                    # Create row dict
                    row_dict = dict(zip(headers, row_data))
                    row_dict['Division'] = division
                    all_teams.append(row_dict)

        if not all_teams:
            raise ValueError("No standings data found on the page")

        # Create DataFrame
        df = pd.DataFrame(all_teams)

        print(f"Successfully extracted {len(df)} team records")
        return df

    def scrape(self):
        """Main scraping method"""
        html = self.fetch_page()
        self.data = self.parse_standings(html)
        self._add_team_names()
        return self.data

    def _add_team_names(self):
        """Add full team names based on mapping and extract team abbreviation"""
        if self.data is None:
            return

        # Find the team column (usually called "Team" or similar)
        team_col = None
        for col in self.data.columns:
            if 'team' in col.lower() and col != 'Team Name':
                team_col = col
                break

        if team_col:
            # The Team column appears to have format "ABBREVFullName"
            # We need to split this into abbreviation and full name
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
                # Usually abbreviations are all caps (2-3 chars) followed by title case
                import re
                match = re.match(r'^([A-Z]{2,4})(.+)$', team_str)
                if match:
                    return match.group(1), match.group(2)

                return team_str, team_str

            # Apply splitting
            self.data[['Team Abbrev', 'Team Name']] = self.data[team_col].apply(
                lambda x: pd.Series(split_team_name(x))
            )

            # Try to map the abbreviation to the full name from mapping
            if self.team_mapping:
                self.data['Team Name Mapped'] = self.data['Team Abbrev'].map(self.team_mapping)

                # Use mapped name if available, otherwise use extracted name
                self.data['Team Name'] = self.data['Team Name Mapped'].fillna(self.data['Team Name'])

                # Drop the temporary column
                self.data.drop('Team Name Mapped', axis=1, inplace=True)

                # Count mapped teams
                mapped_count = self.data['Team Abbrev'].map(self.team_mapping).notna().sum()
                print(f"Added Team Abbrev and Team Name columns: {mapped_count}/{len(self.data)} teams mapped from lookup")

    def export_to_csv(self, filename=None):
        """Export data to CSV file"""
        if self.data is None:
            raise ValueError("No data to export. Run scrape() first.")

        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"output/team_standings_{timestamp}.csv"

        # Ensure output directory exists
        Path("output").mkdir(exist_ok=True)

        self.data.to_csv(filename, index=False)
        print(f"Team standings exported to {filename}")
        return filename


def main():
    # URL to scrape
    url = "https://www.mystatsonline.com/hockey/visitor/league/standings/standings_hockey.aspx?IDLeague=6894"

    # Create scraper instance
    scraper = TeamStandingsScraper(url)

    # Scrape the data
    data = scraper.scrape()

    # Display preview
    print("\n" + "="*50)
    print("TEAM STANDINGS PREVIEW")
    print("="*50)
    print(data.head())
    print(f"\nTotal columns: {len(data.columns)}")
    print(f"Columns: {', '.join(data.columns.tolist())}")

    # Export to CSV
    print("\n" + "="*50)
    csv_file = scraper.export_to_csv()

    print("\n" + "="*50)
    print("TEAM STANDINGS SCRAPING COMPLETE!")
    print("="*50)


if __name__ == "__main__":
    main()
