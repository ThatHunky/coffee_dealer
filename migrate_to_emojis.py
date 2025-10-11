"""
Database migration script: Convert hex colors to emojis.

This script migrates the database from the old color-based system
to the new emoji-based system.

Run this script ONCE after updating to the emoji version:
    python migrate_to_emojis.py
"""

import sqlite3
from pathlib import Path

# Color to emoji mapping
COLOR_TO_EMOJI = {
    "#4A90E2": "🔵",  # Blue -> Blue circle
    "#9B59B6": "🟣",  # Purple -> Purple circle
    "#27AE60": "🟢",  # Green -> Green circle
    "#E74C3C": "🔴",  # Red -> Red circle
    "#E91E63": "🩷",  # Pink -> Pink heart
    "#F39C12": "🟡",  # Orange -> Yellow circle
    "#95A5A6": "⚫",  # Gray -> Black circle (default)
}


def migrate_database(db_path: str = "data/schedule.db"):
    """Migrate database from colors to emojis."""
    db_file = Path(db_path)

    if not db_file.exists():
        print(f"❌ Database not found: {db_path}")
        print("ℹ️  Database will be created with emojis on first run.")
        return

    print(f"🔄 Migrating database: {db_path}")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Check if we need to migrate
    try:
        # Check if old column exists
        cursor.execute("PRAGMA table_info(user_configs)")
        columns = [row[1] for row in cursor.fetchall()]

        if "emoji" in columns and "color_solo" not in columns:
            print("✅ Database already migrated to emojis!")
            conn.close()
            return

        if "color_solo" not in columns:
            print("ℹ️  Fresh database detected, no migration needed.")
            conn.close()
            return

        # Migrate user_configs table
        print("📝 Migrating user_configs table...")

        # Add emoji column
        cursor.execute("ALTER TABLE user_configs ADD COLUMN emoji TEXT DEFAULT '🔵'")

        # Copy color_solo to emoji with mapping
        cursor.execute("SELECT id, color_solo FROM user_configs")
        users = cursor.fetchall()

        for user_id, color_solo in users:
            emoji = COLOR_TO_EMOJI.get(color_solo, "⚫")
            cursor.execute(
                "UPDATE user_configs SET emoji = ? WHERE id = ?", (emoji, user_id)
            )
            print(f"   User {user_id}: {color_solo} → {emoji}")

        # Drop old column (SQLite doesn't support DROP COLUMN in older versions)
        # We'll keep it for now and just use emoji going forward

        # Migrate combination_colors table
        print("\n📝 Migrating combination_colors table...")

        cursor.execute("PRAGMA table_info(combination_colors)")
        combo_columns = [row[1] for row in cursor.fetchall()]

        if "color" in combo_columns:
            # Add emoji column
            cursor.execute(
                "ALTER TABLE combination_colors ADD COLUMN emoji TEXT DEFAULT '⚫'"
            )

            # Copy color to emoji with mapping
            cursor.execute("SELECT id, color FROM combination_colors")
            combos = cursor.fetchall()

            for combo_id, color in combos:
                emoji = COLOR_TO_EMOJI.get(color, "⚫")
                cursor.execute(
                    "UPDATE combination_colors SET emoji = ? WHERE id = ?",
                    (emoji, combo_id),
                )
                print(f"   Combo {combo_id}: {color} → {emoji}")

        conn.commit()
        print("\n✅ Migration completed successfully!")
        print("\nℹ️  Note: Old 'color_solo' and 'color' columns are preserved.")
        print("   You can manually remove them if desired using SQLite tools.")

    except sqlite3.Error as e:
        print(f"❌ Migration failed: {e}")
        conn.rollback()
    finally:
        conn.close()


if __name__ == "__main__":
    print("🎨 Coffee Dealer Bot - Color to Emoji Migration")
    print("=" * 50)
    migrate_database()
    print("\n" + "=" * 50)
    print("Done! You can now start the bot with emoji support.")
