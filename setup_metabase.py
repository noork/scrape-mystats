#!/usr/bin/env python3
"""
Setup Metabase with saved questions and dashboard for Hockey Stats
Run this after completing Metabase initial setup.
"""
import requests
import json
import sys

METABASE_URL = "http://localhost:3000"

def get_session(email, password):
    """Authenticate and get session token"""
    resp = requests.post(f"{METABASE_URL}/api/session", json={
        "username": email,
        "password": password
    })
    if resp.status_code != 200:
        print(f"Login failed: {resp.text}")
        sys.exit(1)
    return resp.json()["id"]

def get_database_id(session):
    """Get the Hockey Stats database ID"""
    resp = requests.get(f"{METABASE_URL}/api/database",
                       headers={"X-Metabase-Session": session})
    databases = resp.json().get("data", resp.json())
    for db in databases:
        if "hockey" in db["name"].lower() or "sqlite" in db.get("engine", "").lower():
            return db["id"]
    # Return first non-sample database
    for db in databases:
        if db.get("is_sample") != True:
            return db["id"]
    return databases[0]["id"] if databases else None

def get_table_ids(session, db_id):
    """Get table IDs for player_stats, games, team_standings"""
    resp = requests.get(f"{METABASE_URL}/api/database/{db_id}/metadata",
                       headers={"X-Metabase-Session": session})
    tables = {}
    for table in resp.json().get("tables", []):
        tables[table["name"]] = table["id"]
    return tables

def create_native_question(session, db_id, name, sql, display="table"):
    """Create a saved question using native SQL"""
    resp = requests.post(f"{METABASE_URL}/api/card",
                        headers={"X-Metabase-Session": session},
                        json={
                            "name": name,
                            "dataset_query": {
                                "type": "native",
                                "native": {"query": sql},
                                "database": db_id
                            },
                            "display": display,
                            "visualization_settings": {}
                        })
    if resp.status_code in [200, 202]:
        print(f"  Created: {name}")
        return resp.json()["id"]
    else:
        print(f"  Failed to create {name}: {resp.text}")
        return None

def create_dashboard(session, name):
    """Create a new dashboard"""
    resp = requests.post(f"{METABASE_URL}/api/dashboard",
                        headers={"X-Metabase-Session": session},
                        json={"name": name})
    if resp.status_code in [200, 202]:
        return resp.json()["id"]
    return None

def add_card_to_dashboard(session, dashboard_id, card_id, row, col, size_x=6, size_y=4):
    """Add a card to a dashboard"""
    resp = requests.post(f"{METABASE_URL}/api/dashboard/{dashboard_id}/cards",
                        headers={"X-Metabase-Session": session},
                        json={
                            "cardId": card_id,
                            "row": row,
                            "col": col,
                            "size_x": size_x,
                            "size_y": size_y
                        })
    return resp.status_code in [200, 202]

def main():
    print("="*60)
    print("Metabase Hockey Stats Setup")
    print("="*60)

    if len(sys.argv) >= 3:
        email = sys.argv[1]
        password = sys.argv[2]
    else:
        email = input("Enter your Metabase email: ")
        password = input("Enter your Metabase password: ")

    print("\nAuthenticating...")
    session = get_session(email, password)
    print("Authenticated!")

    print("\nFinding database...")
    db_id = get_database_id(session)
    if not db_id:
        print("No database found! Make sure you added the SQLite database.")
        sys.exit(1)
    print(f"Using database ID: {db_id}")

    print("\nCreating saved questions...")
    questions = {}

    # 1. Top Scorers
    questions["top_scorers"] = create_native_question(session, db_id,
        "Top 10 Scorers",
        """SELECT PLAYERS as Player, "Team Name" as Team,
                  CAST(PTS as INTEGER) as Points,
                  CAST(G as INTEGER) as Goals,
                  CAST(A as INTEGER) as Assists,
                  CAST(GP as INTEGER) as "Games Played"
           FROM player_stats
           WHERE PTS IS NOT NULL AND PTS != ''
           ORDER BY CAST(PTS as INTEGER) DESC
           LIMIT 10""",
        "bar")

    # 2. Goals vs Assists (scatter)
    questions["goals_vs_assists"] = create_native_question(session, db_id,
        "Goals vs Assists",
        """SELECT PLAYERS as Player, "Team Name" as Team,
                  CAST(G as INTEGER) as Goals,
                  CAST(A as INTEGER) as Assists
           FROM player_stats
           WHERE G IS NOT NULL AND A IS NOT NULL
                 AND G != '' AND A != ''""",
        "scatter")

    # 3. Team Points Comparison
    questions["team_comparison"] = create_native_question(session, db_id,
        "Team Points Comparison",
        """SELECT "Team Name" as Team,
                  SUM(CAST(PTS as INTEGER)) as "Total Points"
           FROM player_stats
           WHERE PTS IS NOT NULL AND PTS != '' AND "Team Name" IS NOT NULL
           GROUP BY "Team Name"
           ORDER BY SUM(CAST(PTS as INTEGER)) DESC""",
        "bar")

    # 4. Stats Distribution - Goals
    questions["goals_distribution"] = create_native_question(session, db_id,
        "Goals Distribution",
        """SELECT CAST(G as INTEGER) as Goals, COUNT(*) as Players
           FROM player_stats
           WHERE G IS NOT NULL AND G != ''
           GROUP BY CAST(G as INTEGER)
           ORDER BY Goals""",
        "bar")

    # 5. Stats Distribution - Assists
    questions["assists_distribution"] = create_native_question(session, db_id,
        "Assists Distribution",
        """SELECT CAST(A as INTEGER) as Assists, COUNT(*) as Players
           FROM player_stats
           WHERE A IS NOT NULL AND A != ''
           GROUP BY CAST(A as INTEGER)
           ORDER BY Assists""",
        "bar")

    # 6. Stats Distribution - Points
    questions["points_distribution"] = create_native_question(session, db_id,
        "Points Distribution",
        """SELECT CAST(PTS as INTEGER) as Points, COUNT(*) as Players
           FROM player_stats
           WHERE PTS IS NOT NULL AND PTS != ''
           GROUP BY CAST(PTS as INTEGER)
           ORDER BY Points""",
        "bar")

    # 7. Position Analysis - Average Points
    questions["position_avg_pts"] = create_native_question(session, db_id,
        "Average Points by Position",
        """SELECT POS as Position,
                  ROUND(AVG(CAST(PTS as REAL)), 2) as "Avg Points",
                  COUNT(*) as "Player Count"
           FROM player_stats
           WHERE PTS IS NOT NULL AND PTS != '' AND POS IS NOT NULL
           GROUP BY POS
           ORDER BY AVG(CAST(PTS as REAL)) DESC""",
        "bar")

    # 8. PIM/GP by Team
    questions["pim_gp_by_team"] = create_native_question(session, db_id,
        "Avg Penalties per Game by Team",
        """SELECT "Team Name" as Team,
                  ROUND(AVG("PIM/GP"), 2) as "Avg PIM/GP",
                  COUNT(*) as Players
           FROM player_stats
           WHERE "PIM/GP" IS NOT NULL AND CAST(GP as INTEGER) > 3
                 AND "Team Name" IS NOT NULL
           GROUP BY "Team Name"
           ORDER BY AVG("PIM/GP") DESC""",
        "bar")

    # 9. Top Players by PIM/GP
    questions["pim_gp_by_player"] = create_native_question(session, db_id,
        "Top 50 Players by Penalties/Game",
        """SELECT PLAYERS as Player, "Team Name" as Team,
                  ROUND("PIM/GP", 2) as "PIM/GP",
                  CAST(GP as INTEGER) as "Games Played"
           FROM player_stats
           WHERE "PIM/GP" IS NOT NULL AND CAST(GP as INTEGER) > 3
           ORDER BY "PIM/GP" DESC
           LIMIT 50""",
        "bar")

    # 10. P/GP by Team
    questions["p_gp_by_team"] = create_native_question(session, db_id,
        "Avg Points per Game by Team",
        """SELECT "Team Name" as Team,
                  ROUND(AVG(CAST("P/GP" as REAL)), 2) as "Avg P/GP",
                  COUNT(*) as Players
           FROM player_stats
           WHERE "P/GP" IS NOT NULL AND CAST(GP as INTEGER) > 3
                 AND "Team Name" IS NOT NULL
           GROUP BY "Team Name"
           ORDER BY AVG(CAST("P/GP" as REAL)) DESC""",
        "bar")

    # 11. Top Players by P/GP
    questions["p_gp_by_player"] = create_native_question(session, db_id,
        "Top 50 Players by Points/Game",
        """SELECT PLAYERS as Player, "Team Name" as Team,
                  ROUND(CAST("P/GP" as REAL), 2) as "P/GP",
                  CAST(GP as INTEGER) as "Games Played",
                  CAST(PTS as INTEGER) as Points
           FROM player_stats
           WHERE "P/GP" IS NOT NULL AND CAST(GP as INTEGER) > 3
           ORDER BY CAST("P/GP" as REAL) DESC
           LIMIT 50""",
        "bar")

    # 12. G/GP by Team
    questions["g_gp_by_team"] = create_native_question(session, db_id,
        "Avg Goals per Game by Team",
        """SELECT "Team Name" as Team,
                  ROUND(AVG(CAST("G/GP" as REAL)), 2) as "Avg G/GP",
                  COUNT(*) as Players
           FROM player_stats
           WHERE "G/GP" IS NOT NULL AND CAST(GP as INTEGER) > 3
                 AND "Team Name" IS NOT NULL
           GROUP BY "Team Name"
           ORDER BY AVG(CAST("G/GP" as REAL)) DESC""",
        "bar")

    # 13. Top Players by G/GP
    questions["g_gp_by_player"] = create_native_question(session, db_id,
        "Top 50 Players by Goals/Game",
        """SELECT PLAYERS as Player, "Team Name" as Team,
                  ROUND(CAST("G/GP" as REAL), 2) as "G/GP",
                  CAST(GP as INTEGER) as "Games Played",
                  CAST(G as INTEGER) as Goals
           FROM player_stats
           WHERE "G/GP" IS NOT NULL AND CAST(GP as INTEGER) > 3
           ORDER BY CAST("G/GP" as REAL) DESC
           LIMIT 50""",
        "bar")

    # 14. Closest Games
    questions["closest_games"] = create_native_question(session, db_id,
        "Closest Games (Smallest Score Differential)",
        """SELECT game_date as Date,
                  away_team_name || ' ' || away_score || ' vs ' || home_team_name || ' ' || home_score as Matchup,
                  ABS(home_score - away_score) as "Score Differential",
                  location as Location
           FROM games
           WHERE away_score IS NOT NULL AND home_score IS NOT NULL
           ORDER BY ABS(home_score - away_score) ASC, game_date DESC
           LIMIT 30""",
        "table")

    # 15. Team Standings
    questions["team_standings"] = create_native_question(session, db_id,
        "Team Standings",
        """SELECT rank as "#", team_name as Team, division as Division,
                  games_played as GP, wins as W, losses as L,
                  points as PTS, pct as PCT,
                  goals_for as GF, goals_against as GA, goal_diff as "+/-",
                  streak as Streak
           FROM team_standings
           ORDER BY rank""",
        "table")

    # 16. Division Summary
    questions["division_summary"] = create_native_question(session, db_id,
        "Division Balance Summary",
        """SELECT division as Division,
                  COUNT(*) as Teams,
                  SUM(wins) as "Total Wins",
                  SUM(losses) as "Total Losses",
                  ROUND(AVG(pct), 3) as "Avg PCT",
                  SUM(goals_for) as "Total GF",
                  SUM(goals_against) as "Total GA"
           FROM team_standings
           GROUP BY division
           ORDER BY AVG(pct) DESC""",
        "bar")

    # 17. Games by Location
    questions["games_by_location"] = create_native_question(session, db_id,
        "Games by Location",
        """SELECT location as Location, COUNT(*) as "Games Played"
           FROM games
           WHERE location IS NOT NULL AND location != ''
           GROUP BY location
           ORDER BY COUNT(*) DESC""",
        "pie")

    # 18. High Scoring Games
    questions["high_scoring_games"] = create_native_question(session, db_id,
        "Highest Scoring Games",
        """SELECT game_date as Date,
                  away_team_name || ' ' || away_score || ' vs ' || home_team_name || ' ' || home_score as Matchup,
                  (away_score + home_score) as "Total Goals",
                  location as Location
           FROM games
           WHERE away_score IS NOT NULL AND home_score IS NOT NULL
           ORDER BY (away_score + home_score) DESC
           LIMIT 20""",
        "table")

    print(f"\nCreated {len([q for q in questions.values() if q])} questions")

    # Create Dashboard
    print("\nCreating dashboard...")
    dashboard_id = create_dashboard(session, "Hockey Stats Dashboard")

    if dashboard_id:
        print(f"Dashboard created with ID: {dashboard_id}")
        print("Adding cards to dashboard...")

        # Layout: 2 columns, questions arranged in grid
        layout = [
            ("top_scorers", 0, 0, 9, 6),
            ("team_standings", 0, 9, 9, 6),
            ("team_comparison", 6, 0, 9, 5),
            ("division_summary", 6, 9, 9, 5),
            ("p_gp_by_team", 11, 0, 9, 5),
            ("g_gp_by_team", 11, 9, 9, 5),
            ("pim_gp_by_team", 16, 0, 9, 5),
            ("position_avg_pts", 16, 9, 9, 5),
            ("closest_games", 21, 0, 9, 6),
            ("high_scoring_games", 21, 9, 9, 6),
            ("goals_vs_assists", 27, 0, 9, 5),
            ("games_by_location", 27, 9, 9, 5),
        ]

        for name, row, col, size_x, size_y in layout:
            if name in questions and questions[name]:
                add_card_to_dashboard(session, dashboard_id, questions[name], row, col, size_x, size_y)

        print("\nDashboard setup complete!")
        print(f"\nOpen your dashboard at: {METABASE_URL}/dashboard/{dashboard_id}")

    print("\n" + "="*60)
    print("Setup Complete!")
    print("="*60)
    print(f"\nYou can now access your dashboard and questions at {METABASE_URL}")
    print("All saved questions are available in the 'Our analytics' section")

if __name__ == "__main__":
    main()
