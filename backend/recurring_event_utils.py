# Save this as: backend/recurring_event_utils.py

from datetime import datetime, timedelta
from typing import List, Dict, Any

def generate_recurring_events(event_details: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Generate individual events from recurring event details
    
    Args:
        event_details: Dictionary containing event details with recurrence info
        
    Returns:
        List of individual event dictionaries
    """
    events = []
    
    # Extract recurrence information
    recurrence_type = event_details.get('recurrence_type', 'daily')
    recurrence_count = event_details.get('recurrence_count', 7)
    recurrence_end_date = event_details.get('recurrence_end_date')
    recurrence_days = event_details.get('recurrence_days', [])
    
    # Base event data
    base_event = {
        'title': event_details['title'],
        'description': event_details.get('description', ''),
        'location': event_details.get('location', ''),
        'importance': event_details.get('importance', 5)
    }
    
    start_time = event_details['start_time']
    end_time = event_details['end_time']
    
    # Calculate duration
    duration = end_time - start_time
    
    if recurrence_type == 'daily':
        # Generate daily events
        current_date = start_time
        count = 0
        
        # If recurrence_count is a string like "7 days", extract the number
        if isinstance(recurrence_count, str):
            import re
            match = re.search(r'(\d+)', str(recurrence_count))
            if match:
                recurrence_count = int(match.group(1))
            else:
                recurrence_count = 7  # default
        
        while count < recurrence_count:
            # Check if we've reached the end date
            if recurrence_end_date and current_date.date() > recurrence_end_date.date():
                break
                
            # Create event for this day
            event = base_event.copy()
            event['start_time'] = current_date
            event['end_time'] = current_date + duration
            
            events.append(event)
            
            # Move to next day
            current_date += timedelta(days=1)
            count += 1
    
    elif recurrence_type == 'weekly':
        # Generate weekly events
        current_date = start_time
        weeks_count = 0
        max_weeks = recurrence_count if isinstance(recurrence_count, int) else 4
        
        # If recurrence_days is specified, use those days
        if recurrence_days:
            # Map day names to weekday numbers
            day_mapping = {
                'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3,
                'friday': 4, 'saturday': 5, 'sunday': 6
            }
            
            target_weekdays = [day_mapping.get(day.lower()) for day in recurrence_days if day_mapping.get(day.lower()) is not None]
            
            while weeks_count < max_weeks:
                # Check each day of the current week
                week_start = current_date - timedelta(days=current_date.weekday())
                
                for weekday in target_weekdays:
                    event_date = week_start + timedelta(days=weekday)
                    event_datetime = event_date.replace(hour=start_time.hour, minute=start_time.minute)
                    
                    # Skip if the date is before our start date
                    if event_datetime < start_time:
                        continue
                    
                    # Check if we've reached the end date
                    if recurrence_end_date and event_datetime.date() > recurrence_end_date.date():
                        break
                    
                    # Create event for this day
                    event = base_event.copy()
                    event['start_time'] = event_datetime
                    event['end_time'] = event_datetime + duration
                    
                    events.append(event)
                
                # Move to next week
                current_date += timedelta(weeks=1)
                weeks_count += 1
        else:
            # Default to same day of week
            while weeks_count < max_weeks:
                # Check if we've reached the end date
                if recurrence_end_date and current_date.date() > recurrence_end_date.date():
                    break
                
                # Create event for this week
                event = base_event.copy()
                event['start_time'] = current_date
                event['end_time'] = current_date + duration
                
                events.append(event)
                
                # Move to next week
                current_date += timedelta(weeks=1)
                weeks_count += 1
    
    elif recurrence_type == 'weekday':
        # Generate events for weekdays only (Monday-Friday)
        current_date = start_time
        count = 0
        max_count = recurrence_count if isinstance(recurrence_count, int) else 5
        
        while count < max_count:
            # Check if we've reached the end date
            if recurrence_end_date and current_date.date() > recurrence_end_date.date():
                break
            
            # Only add if it's a weekday (Monday=0, Sunday=6)
            if current_date.weekday() < 5:  # 0-4 are weekdays
                event = base_event.copy()
                event['start_time'] = current_date
                event['end_time'] = current_date + duration
                
                events.append(event)
                count += 1
            
            # Move to next day
            current_date += timedelta(days=1)
    
    return events

def parse_recurrence_from_text(text: str) -> Dict[str, Any]:
    """
    Parse recurrence information from natural language text
    
    Args:
        text: Natural language description of recurrence
        
    Returns:
        Dictionary with recurrence information
    """
    text = text.lower()
    recurrence_info = {}
    
    # Detect recurrence type
    if 'every day' in text or 'daily' in text:
        recurrence_info['recurrence_type'] = 'daily'
    elif 'every week' in text or 'weekly' in text:
        recurrence_info['recurrence_type'] = 'weekly'
    elif 'weekday' in text or 'monday to friday' in text or 'mon-fri' in text:
        recurrence_info['recurrence_type'] = 'weekday'
    else:
        recurrence_info['recurrence_type'] = 'daily'  # default
    
    # Detect count
    import re
    
    # Look for patterns like "for 7 days", "for a week", "for 2 weeks"
    count_patterns = [
        r'for (\d+) days?',
        r'for (\d+) weeks?',
        r'for a week',
        r'for the week',
        r'(\d+) times?'
    ]
    
    for pattern in count_patterns:
        match = re.search(pattern, text)
        if match:
            if 'week' in pattern and match.group(0):
                if 'a week' in match.group(0) or 'the week' in match.group(0):
                    recurrence_info['recurrence_count'] = 7 if 'daily' in recurrence_info.get('recurrence_type', '') else 1
                else:
                    weeks = int(match.group(1))
                    recurrence_info['recurrence_count'] = weeks * 7 if 'daily' in recurrence_info.get('recurrence_type', '') else weeks
            else:
                recurrence_info['recurrence_count'] = int(match.group(1))
            break
    
    # Default count if not found
    if 'recurrence_count' not in recurrence_info:
        if 'week' in text:
            recurrence_info['recurrence_count'] = 7 if recurrence_info['recurrence_type'] == 'daily' else 1
        else:
            recurrence_info['recurrence_count'] = 7
    
    # Detect specific days for weekly events
    day_patterns = {
        'monday': r'\bmonday\b|\bmon\b',
        'tuesday': r'\btuesday\b|\btue\b',
        'wednesday': r'\bwednesday\b|\bwed\b',
        'thursday': r'\bthursday\b|\bthu\b',
        'friday': r'\bfriday\b|\bfri\b',
        'saturday': r'\bsaturday\b|\bsat\b',
        'sunday': r'\bsunday\b|\bsun\b'
    }
    
    recurrence_days = []
    for day, pattern in day_patterns.items():
        if re.search(pattern, text):
            recurrence_days.append(day)
    
    if recurrence_days:
        recurrence_info['recurrence_days'] = recurrence_days
    
    return recurrence_info