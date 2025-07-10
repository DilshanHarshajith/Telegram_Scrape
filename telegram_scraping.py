# Basic Setup
from telethon import TelegramClient, events, sync, errors
from telethon.tl.functions.channels import GetFullChannelRequest
from telethon.tl.functions.messages import GetHistoryRequest
from telethon.tl.types import PeerChannel, InputPhoneContact
import asyncio
import pandas as pd
from datetime import datetime
import os
import logging
import time
from tqdm import tqdm
import sys
from dotenv import load_dotenv
import re

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("telegram_scraper.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()

# Get API credentials from environment variables or prompt user
api_id = os.getenv('TELEGRAM_API_ID')
api_hash = os.getenv('TELEGRAM_API_HASH')
phone_number = os.getenv('TELEGRAM_PHONE')

if not api_id or not api_hash or not phone_number:
    print("API credentials not found in environment variables.")
    api_id = input("Please enter your API ID: ")
    api_hash = input("Please enter your API hash: ")
    phone_number = input("Please enter your phone number (with country code): ")

# Read channels from file with error handling
def read_channels_from_file(file_path="list.txt"):
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            channels = [line.strip() for line in file.readlines() if line.strip()]
        if not channels:
            logger.warning(f"No channels found in {file_path}")
        return channels
    except FileNotFoundError:
        logger.error(f"Channel list file '{file_path}' not found.")
        # Create an empty file for the user to fill in
        with open(file_path, "w", encoding="utf-8") as file:
            file.write("# Add one channel username per line (with or without @)\n")
        logger.info(f"Created empty '{file_path}' file. Please add channel usernames and run again.")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error reading channel list: {e}")
        sys.exit(1)

channels = read_channels_from_file()

# Initialize the client with session file in a dedicated directory
os.makedirs("sessions", exist_ok=True)
client = TelegramClient(os.path.join("sessions", "telegram_scraper_session"), api_id, api_hash)

# 3. Basic Connection with improved error handling
async def basic_connection():
    try:
        # Connect to the client
        await client.connect()
        
        # If not authorized, send code request
        if not await client.is_user_authorized():
            await client.send_code_request(phone_number)
            # Sign in with the code received
            code = input('Enter the code you received: ')
            try:
                await client.sign_in(phone_number, code)
            except errors.SessionPasswordNeededError:
                # Handle 2FA
                password = input("Two-factor authentication enabled. Please enter your password: ")
                await client.sign_in(password=password)
        
        # Get information about yourself
        me = await client.get_me()
        logger.info(f"Successfully connected as {me.first_name}")
        return True
    except errors.PhoneNumberInvalidError:
        logger.error("Invalid phone number format. Please include the country code.")
        return False
    except errors.ApiIdInvalidError:
        logger.error("Invalid API credentials. Check your API ID and hash.")
        return False
    except Exception as e:
        logger.error(f"Connection error: {e}")
        return False

# Helper function to implement rate limiting
async def rate_limited_operation(operation, *args, **kwargs):
    """Execute an operation with rate limiting to avoid hitting Telegram's limits"""
    max_retries = 5
    base_delay = 2  # seconds
    
    for retry in range(max_retries):
        try:
            return await operation(*args, **kwargs)
        except errors.FloodWaitError as e:
            wait_time = e.seconds
            logger.warning(f"Rate limit hit. Waiting for {wait_time} seconds.")
            await asyncio.sleep(wait_time)
        except (errors.ServerError, errors.TimedOutError) as e:
            delay = base_delay * (2 ** retry)
            logger.warning(f"Server error: {e}. Retrying in {delay} seconds...")
            await asyncio.sleep(delay)
    
    # If we've exhausted all retries
    logger.error("Operation failed after maximum retries")
    return None

# 4. Improved Scrape Messages from a Channel
async def scrape_channel_messages(channel_username, limit=100):
    """
    Scrape recent messages from a public channel with improved error handling and rate limiting
    
    Args:
        channel_username: Username of the channel (with or without @)
        limit: Maximum number of messages to retrieve
        
    Returns:
        DataFrame containing the scraped messages
    """
    try:
        # Ensure the username format is correct
        if channel_username.startswith('@'):
            channel_username = channel_username[1:]
        
        # Get the channel entity
        try:
            channel = await rate_limited_operation(client.get_entity, channel_username)
        except (errors.UsernameNotOccupiedError, ValueError):
            logger.error(f"Channel @{channel_username} not found. Skipping.")
            return pd.DataFrame()
            
        # Collect messages
        all_messages = []
        
        # Use GetHistoryRequest for more control
        offset_id = 0
        total_messages = 0
        limit_per_request = min(100, limit)
        
        with tqdm(total=limit, desc=f"Scraping @{channel_username}") as pbar:
            while total_messages < limit:
                history = await rate_limited_operation(client, GetHistoryRequest(
                    peer=channel,
                    offset_id=offset_id,
                    offset_date=None,
                    add_offset=0,
                    limit=limit_per_request,
                    max_id=0,
                    min_id=0,
                    hash=0
                ))
                
                if not history or not history.messages:
                    break
                    
                messages = history.messages
                for message in messages:
                    message_data = {
                        'id': message.id,
                        'date': message.date,
                        'text': message.message if message.message else "",
                        'views': getattr(message, 'views', 0),
                        'forwards': getattr(message, 'forwards', 0),
                        'replies': getattr(message, 'replies', 0) if hasattr(message, 'replies') else 0,
                        'has_media': bool(message.media),
                        'media_type': str(type(message.media).__name__) if message.media else None,
                        'channel': channel_username
                    }
                    
                    # Get sender info if available
                    if hasattr(message, 'sender_id') and message.sender_id:
                        try:
                            sender = await client.get_entity(message.sender_id)
                            message_data['sender_id'] = sender.id
                            message_data['sender_name'] = getattr(sender, 'first_name', '') + ' ' + getattr(sender, 'last_name', '')
                            message_data['sender_username'] = getattr(sender, 'username', '')
                        except Exception as e:
                            # Unable to get sender details
                            message_data['sender_id'] = message.sender_id
                            message_data['sender_name'] = "Unknown"
                            message_data['sender_username'] = "Unknown"
                    
                    all_messages.append(message_data)
                    
                if messages:
                    offset_id = messages[-1].id
                    pbar.update(len(messages))
                    total_messages += len(messages)
                    
                    # Be nice to Telegram servers
                    await asyncio.sleep(0.5)
                
                if len(messages) < limit_per_request:
                    break
        
        # Convert to DataFrame
        if all_messages:
            df = pd.DataFrame(all_messages)
            return df
        else:
            logger.warning(f"No messages found in @{channel_username}")
            return pd.DataFrame()
            
    except Exception as e:
        logger.error(f"Error scraping channel @{channel_username}: {e}")
        return pd.DataFrame()

# 5. Improved Download Media from Messages
async def download_media_from_channel(channel_username, folder="downloads", limit=100):
    """
    Download media files from a channel with improved handling
    
    Args:
        channel_username: Username of the channel
        limit: Maximum number of messages to check for media
        folder: Base folder to save downloaded media
    """
    try:
        # Create download directory if it doesn't exist
        channel_folder = os.path.join(folder, re.sub(r'[^\w\-_]', '_', channel_username))
        os.makedirs(channel_folder, exist_ok=True)
        
        # Get channel entity
        if channel_username.startswith('@'):
            channel_username = channel_username[1:]
        
        try:
            channel = await rate_limited_operation(client.get_entity, channel_username)
        except (errors.UsernameNotOccupiedError, ValueError):
            logger.error(f"Channel @{channel_username} not found. Skipping media download.")
            return
        
        # Get messages with media
        downloaded = 0
        skipped = 0
        
        with tqdm(total=limit, desc=f"Checking media in @{channel_username}") as pbar:
            async for i, message in enumerate(client.iter_messages(channel, limit=limit)):
                pbar.update(1)
                
                if message.media:
                    # Create a filename based on message date and ID for uniqueness
                    date_str = message.date.strftime('%Y%m%d_%H%M%S')
                    base_filename = f"{date_str}_{message.id}"
                    
                    try:
                        # Download with progress feedback
                        print(f"\nDownloading media from message {message.id}...")
                        file_path = await rate_limited_operation(
                            client.download_media,
                            message.media,
                            os.path.join(channel_folder, base_filename)
                        )
                        
                        if file_path:
                            downloaded += 1
                            print(f"Downloaded to {file_path}")
                        else:
                            skipped += 1
                            logger.warning(f"Couldn't download media from message {message.id}")
                    except Exception as e:
                        skipped += 1
                        logger.error(f"Error downloading media from message {message.id}: {e}")
                
                # Be nice to Telegram servers
                if i % 10 == 0:
                    await asyncio.sleep(0.5)
        
        logger.info(f"Downloaded {downloaded} media files, skipped {skipped} files")
    
    except Exception as e:
        logger.error(f"Error downloading media from channel @{channel_username}: {e}")

# 6. Monitor a Channel for New Messages
async def monitor_channel(channel_username, duration_seconds=60):
    """
    Monitor a channel for new messages for a specified duration
    
    Args:
        channel_username: Username of the channel
        duration_seconds: How long to monitor (in seconds)
    """
    try:
        # Get channel entity
        if channel_username.startswith('@'):
            channel_username = channel_username[1:]
        
        try:
            channel = await rate_limited_operation(client.get_entity, channel_username)
        except (errors.UsernameNotOccupiedError, ValueError):
            logger.error(f"Channel @{channel_username} not found. Cannot monitor.")
            return
        
        # Create event handler
        @client.on(events.NewMessage(chats=channel))
        async def new_message_handler(event):
            message = event.message
            logger.info(f"New message in @{channel_username} [{message.id}]: {message.message[:50]}...")
            if message.media:
                logger.info(f"Message contains media of type: {type(message.media).__name__}")
        
        logger.info(f"Monitoring channel @{channel_username} for {duration_seconds} seconds...")
        await asyncio.sleep(duration_seconds)
        
        # Remove the event handler
        client.remove_event_handler(new_message_handler)
        logger.info("Monitoring complete")
    
    except Exception as e:
        logger.error(f"Error monitoring channel @{channel_username}: {e}")

# 7. Improved Search for Messages
async def search_messages(channel_username, query, limit=100):
    """
    Search for messages containing specific text with improved handling
    
    Args:
        channel_username: Username of the channel
        query: Text to search for
        limit: Maximum number of messages to search through
    
    Returns:
        DataFrame of matching messages
    """
    try:
        # Get channel entity
        if channel_username.startswith('@'):
            channel_username = channel_username[1:]
        
        try:
            channel = await rate_limited_operation(client.get_entity, channel_username)
        except (errors.UsernameNotOccupiedError, ValueError):
            logger.error(f"Channel @{channel_username} not found. Cannot search.")
            return pd.DataFrame()
        
        # Search messages
        matching_messages = []
        
        with tqdm(total=limit, desc=f"Searching in @{channel_username}") as pbar:
            async for message in client.iter_messages(channel, limit=limit, search=query):
                matching_messages.append({
                    'id': message.id,
                    'date': message.date,
                    'text': message.message if message.message else "",
                    'views': getattr(message, 'views', 0),
                    'channel': channel_username,
                    'has_media': bool(message.media)
                })
                pbar.update(1)
                
                # Be nice to Telegram servers
                if len(matching_messages) % 20 == 0:
                    await asyncio.sleep(0.5)
        
        # Convert to DataFrame
        if matching_messages:
            df = pd.DataFrame(matching_messages)
            logger.info(f"Found {len(df)} messages matching '{query}' in @{channel_username}")
            return df
        else:
            logger.info(f"No messages found matching '{query}' in @{channel_username}")
            return pd.DataFrame()
    
    except Exception as e:
        logger.error(f"Error searching in channel @{channel_username}: {e}")
        return pd.DataFrame()

# 8. Improved Get Channel Information
async def get_channel_info(channel_username):
    """
    Get information about a channel with better error handling
    
    Args:
        channel_username: Username of the channel
    
    Returns:
        Dictionary with channel information
    """
    try:
        # Get channel entity
        if channel_username.startswith('@'):
            channel_username = channel_username[1:]
        
        try:
            channel = await rate_limited_operation(client.get_entity, channel_username)
        except (errors.UsernameNotOccupiedError, ValueError):
            logger.error(f"Channel @{channel_username} not found.")
            return None
        
        # Gather channel info
        channel_info = {
            'id': channel.id,
            'title': channel.title,
            'username': channel.username,
            'about': getattr(channel, 'about', None),
            'participants_count': None,
            'linked_chat_id': None,
            'last_checked': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        # Try to get participant count and other details (works only for some channels)
        try:
            full_channel = await rate_limited_operation(client, GetFullChannelRequest(channel))
            channel_info['participants_count'] = full_channel.full_chat.participants_count
            channel_info['linked_chat_id'] = full_channel.full_chat.linked_chat_id if hasattr(full_channel.full_chat, 'linked_chat_id') else None
        except Exception as e:
            logger.warning(f"Couldn't get full channel info for @{channel_username}: {e}")
        
        return channel_info
    
    except Exception as e:
        logger.error(f"Error getting info for channel @{channel_username}: {e}")
        return None

# 9. Improved Export Data to CSV/Excel
def export_data(data, filename_prefix, format="csv"):
    """
    Export DataFrame to CSV or Excel
    
    Args:
        data: DataFrame to export
        filename_prefix: Prefix for the output file
        format: "csv" or "excel"
    """
    if not isinstance(data, pd.DataFrame) or data.empty:
        logger.warning(f"No data to export for {filename_prefix}")
        return None
    
    # Create output directory
    os.makedirs("output", exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = os.path.join("output", f"{filename_prefix}_{timestamp}")
    
    try:
        if format.lower() == "csv":
            file_path = f"{filename}.csv"
            data.to_csv(file_path, index=False, encoding='utf-8-sig')
        elif format.lower() == "excel":
            file_path = f"{filename}.xlsx"
            data.to_excel(file_path, index=False, engine='openpyxl')
        else:
            logger.error(f"Unknown export format: {format}")
            return None
            
        logger.info(f"Data exported to {file_path}")
        return file_path
    except Exception as e:
        logger.error(f"Error exporting data: {e}")
        return None

# 10. Complete Example with improved structure
async def process_channel(channel_username, options):
    """Process a single channel based on provided options"""
    try:
        logger.info(f"Processing channel: {channel_username}")
        
        # Get channel info
        channel_info = await get_channel_info(channel_username)
        if not channel_info:
            logger.warning(f"Skipping channel {channel_username} due to errors")
            return False
            
        logger.info(f"Channel: {channel_info['title']} (@{channel_info['username']})")
        
        results = {}
        
        # Scrape messages if requested
        if options.get('scrape_messages', True):
            message_limit = options.get('message_limit', 100)
            messages_df = await scrape_channel_messages(channel_username, limit=message_limit)
            results['messages'] = messages_df
            if not messages_df.empty:
                export_data(messages_df, f"{channel_username}_messages", options.get('export_format', 'csv'))
        
        # Search for messages if requested
        if options.get('search_query'):
            search_df = await search_messages(channel_username, options['search_query'], limit=options.get('search_limit', 500))
            results['search'] = search_df
            if not search_df.empty:
                export_data(search_df, f"{channel_username}_search_{options['search_query']}", options.get('export_format', 'csv'))
        
        # Download media if requested
        if options.get('download_media', False):
            media_limit = options.get('media_limit', 20)
            await download_media_from_channel(channel_username, folder="downloads", limit=media_limit)
        
        # Monitor for new messages if requested
        if options.get('monitor', False):
            monitor_duration = options.get('monitor_duration', 60)
            await monitor_channel(channel_username, duration_seconds=monitor_duration)
        
        return results
    
    except Exception as e:
        logger.error(f"Error processing channel {channel_username}: {e}")
        return False

async def main():
    """Main function with command-line arguments"""
    # Parse options (could be replaced with argparse in a more complete version)
    options = {
        'scrape_messages': True,
        'message_limit': 50,
        'download_media': True,
        'media_limit': 20,
        'export_format': 'csv'
    }
    
    # First establish connection
    if not await basic_connection():
        logger.error("Failed to establish connection. Exiting.")
        return
    
    # Process each channel
    channel_info_list = []
    for channel_username in channels:
        # Get basic info for all channels first
        channel_info = await get_channel_info(channel_username)
        if channel_info:
            channel_info_list.append(channel_info)
    
    # Export channel info
    if channel_info_list:
        channels_df = pd.DataFrame(channel_info_list)
        export_data(channels_df, "all_channels_info", options['export_format'])
    
    # Now process each channel in detail
    for channel_username in channels:
        await process_channel(channel_username, options)
    
    # Disconnect when done
    await client.disconnect()
    logger.info("Script completed successfully")

# Allow running as a standalone script or imported as a module
if __name__ == '__main__':
    try:
        loop = asyncio.get_event_loop()
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        logger.info("Script interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.critical(f"Unhandled exception: {e}")
        sys.exit(1)