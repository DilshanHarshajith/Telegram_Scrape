# Telegram Channel Scraper

A comprehensive Python tool for scraping messages, media, and metadata from Telegram channels using the Telethon library. This tool provides robust error handling, rate limiting, and multiple export formats.

## Features

- **Message Scraping**: Extract messages from public Telegram channels
- **Media Downloads**: Download images, videos, and other media files
- **Channel Monitoring**: Real-time monitoring for new messages
- **Search Functionality**: Search for specific keywords within channels
- **Channel Information**: Get detailed channel metadata
- **Export Options**: Save data in CSV or Excel formats
- **Rate Limiting**: Built-in protection against Telegram API limits
- **Batch Processing**: Process multiple channels from a list
- **Comprehensive Logging**: Detailed logging for troubleshooting

## Prerequisites

- Python 3.7 or higher
- Telegram API credentials (API ID and API Hash)
- A Telegram account with phone number

## Installation

1. **Clone or download the project files**
2. **Install required dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Get Telegram API credentials:**
   - Go to https://my.telegram.org/apps
   - Log in with your Telegram account
   - Create a new application
   - Note down your `API ID` and `API Hash`

## Setup

### Environment Variables (Recommended)

Create a `.env` file in the project directory:

```env
TELEGRAM_API_ID=your_api_id_here
TELEGRAM_API_HASH=your_api_hash_here
TELEGRAM_PHONE=+1234567890
```

### Channel List

Create a `list.txt` file with channel usernames (one per line):

```
@channelname1
@channelname2
channelname3
```

Note: The `@` symbol is optional.

## Usage

### Basic Usage

Run the script with default settings:

```bash
python telegram_scraping.py
```

### Configuration Options

You can modify the `options` dictionary in the `main()` function to customize behavior:

```python
options = {
    'scrape_messages': True,      # Enable message scraping
    'message_limit': 50,          # Number of messages to scrape
    'download_media': True,       # Enable media downloads
    'media_limit': 20,            # Number of media files to download
    'export_format': 'csv',       # Export format: 'csv' or 'excel'
    'search_query': 'keyword',    # Search for specific text (optional)
    'search_limit': 500,          # Messages to search through
    'monitor': False,             # Enable real-time monitoring
    'monitor_duration': 60        # Monitoring duration in seconds
}
```

## Output Structure

The script creates the following directories and files:

```
project_root/
├── sessions/                    # Telegram session files
├── output/                      # Exported data files
│   ├── channelname_messages_YYYYMMDD_HHMMSS.csv
│   └── all_channels_info_YYYYMMDD_HHMMSS.csv
├── downloads/                   # Downloaded media files
│   └── channelname/
│       ├── YYYYMMDD_HHMMSS_messageid.jpg
│       └── ...
├── telegram_scraper.log        # Application logs
└── list.txt                    # Channel list
```

## Data Fields

### Message Data
- `id`: Message ID
- `date`: Message timestamp
- `text`: Message content
- `views`: View count
- `forwards`: Forward count
- `replies`: Reply count
- `has_media`: Boolean indicating media presence
- `media_type`: Type of media (if any)
- `channel`: Channel username
- `sender_id`: Sender's user ID
- `sender_name`: Sender's name
- `sender_username`: Sender's username

### Channel Information
- `id`: Channel ID
- `title`: Channel title
- `username`: Channel username
- `about`: Channel description
- `participants_count`: Number of subscribers
- `linked_chat_id`: Associated chat ID
- `last_checked`: Last check timestamp

## Error Handling

The script includes comprehensive error handling for:

- **Rate Limiting**: Automatic retry with exponential backoff
- **Network Issues**: Timeout and server error handling
- **Invalid Channels**: Graceful handling of non-existent channels
- **API Errors**: Proper handling of Telegram API errors
- **Authentication**: 2FA support and session management

## Rate Limiting

The script implements several rate limiting strategies:

- Delays between requests to avoid hitting API limits
- Exponential backoff for rate limit errors
- Automatic handling of `FloodWaitError`
- Configurable retry attempts

## Logging

Logs are written to both console and `telegram_scraper.log` file with different levels:

- **INFO**: General operation information
- **WARNING**: Non-critical issues
- **ERROR**: Recoverable errors
- **CRITICAL**: Fatal errors

## Common Issues and Solutions

### Authentication Issues
- **Problem**: "Invalid phone number format"
- **Solution**: Include country code (e.g., +1234567890)

### Channel Access
- **Problem**: "Channel not found"
- **Solution**: Ensure channel is public and username is correct

### Rate Limiting
- **Problem**: "Rate limit hit"
- **Solution**: The script handles this automatically, but you can reduce limits if needed

### Media Download Failures
- **Problem**: Some media files fail to download
- **Solution**: Check file permissions and available disk space

## Advanced Usage

### Custom Search
```python
# Search for specific keywords
search_df = await search_messages("channelname", "keyword", limit=1000)
```

### Real-time Monitoring
```python
# Monitor channel for 5 minutes
await monitor_channel("channelname", duration_seconds=300)
```

### Batch Processing
The script automatically processes all channels listed in `list.txt`.

## Legal and Ethical Considerations

- **Respect Terms of Service**: Ensure compliance with Telegram's ToS
- **Rate Limiting**: Don't overwhelm Telegram's servers
- **Privacy**: Respect user privacy and channel rules
- **Public Channels Only**: This tool works with public channels
- **Data Usage**: Use scraped data responsibly and ethically

## Troubleshooting

### Session Issues
Delete the `sessions/` directory and re-authenticate if you encounter persistent login issues.

### API Credentials
Verify your API credentials are correct and the application is properly configured on my.telegram.org.

### Python Version
Ensure you're using Python 3.7 or higher for compatibility.

## Contributing

Feel free to submit issues, feature requests, or pull requests to improve the tool.

## License

This project is for educational and research purposes. Please ensure compliance with applicable laws and Telegram's Terms of Service.

## Support

For issues or questions:
1. Check the log file for detailed error messages
2. Verify your setup follows the installation guide
3. Ensure your API credentials are valid
4. Review the channel list format

---

**Note**: This tool is designed for legitimate research and data collection purposes. Always respect privacy, terms of service, and applicable laws when scraping data.