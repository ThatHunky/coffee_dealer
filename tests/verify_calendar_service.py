import asyncio
import sys
import os
from datetime import date

# Add project root to path
sys.path.append(os.getcwd())

from bot.services.calendar import generate_calendar_image

async def main():
    print("Testing generate_calendar_image...")
    try:
        # Generate for current month
        today = date.today()
        image_file = await generate_calendar_image(today.year, today.month)
        
        # Save to file to verify
        output_path = "tests/verified_calendar.png"
        with open(output_path, "wb") as f:
            f.write(image_file.data)
            
        print(f"Success! Calendar saved to {output_path}")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
