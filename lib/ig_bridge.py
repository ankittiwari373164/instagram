#!/usr/bin/env python3
"""
lib/ig_bridge.py - Instagram API Bridge using instagrapi
Handles: login, search, DM sending, inbox checking
Output: JSON responses for Node.js
"""

import json
import sys
import os
from pathlib import Path
from instagrapi import Client
from instagrapi.exceptions import (
    LoginRequired,
    InvalidPassword,
    PleaseLoginAgain,
    UserNotFound,
    UserIdNotInteger,
    ChallengeRequired,
)

def classify_error(e):
    """Classify error type"""
    msg = str(e).lower()
    if 'challenge' in msg or 'checkpoint' in msg:
        return 'session_expired'
    if 'rate' in msg or '429' in msg:
        return 'rate_limited'
    if 'invalid' in msg or 'password' in msg or '401' in msg:
        return 'login_failed'
    if 'not found' in msg or 'user_not_found' in msg:
        return 'user_not_found'
    if 'block' in msg or 'restricted' in msg:
        return 'blocked'
    if 'spam' in msg or 'action_blocked' in msg:
        return 'spam_detected'
    return 'unknown'

def json_response(ok, **kwargs):
    """Generate standardized JSON response"""
    response = {'ok': ok}
    response.update(kwargs)
    print(json.dumps(response))
    sys.exit(0)

def json_error(error_msg, reason='unknown', **kwargs):
    """Generate error response"""
    response = {
        'ok': False,
        'error': error_msg,
        'reason': reason,
    }
    response.update(kwargs)
    print(json.dumps(response))
    sys.exit(1)

def cmd_login(username, password, session_dir):
    """Login and save session"""
    try:
        print(f'[ig_bridge] Logging in as @{username}...', file=sys.stderr)
        
        # Create client
        cl = Client()
        
        # Login
        cl.login(username, password)
        print(f'[ig_bridge] ✅ Login successful! User ID: {cl.user_id}', file=sys.stderr)
        
        # Get user info
        try:
            user_info = cl.account_info()
            follower_count = user_info.follower_count or 0
        except:
            follower_count = 0
        
        # Save session
        try:
            session_file = Path(session_dir) / f'session_{username.lower()}.json'
            session_file.parent.mkdir(parents=True, exist_ok=True)
            cl.dump_settings(str(session_file))
            print(f'[ig_bridge] Session saved: {session_file}', file=sys.stderr)
        except Exception as e:
            print(f'[ig_bridge] Warning: Could not save session: {e}', file=sys.stderr)
        
        json_response(
            True,
            username=username.lower(),
            user_id=str(cl.user_id),
            follower_count=follower_count,
            method='password'
        )
    
    except InvalidPassword:
        json_error('Invalid password', reason='login_failed')
    except LoginRequired:
        json_error('Login required', reason='login_failed')
    except Exception as e:
        json_error(str(e), reason=classify_error(e))

def cmd_search(username, password, keyword, session_dir):
    """Search for users"""
    try:
        print(f'[ig_bridge] Searching for "{keyword}" as @{username}...', file=sys.stderr)
        
        # Create and login
        cl = Client()
        cl.login(username, password)
        
        users = set()
        
        # Try hashtag search (most reliable)
        try:
            print(f'[ig_bridge] Hashtag search: #{keyword}', file=sys.stderr)
            medias = cl.hashtag_medias_recent(keyword.replace(' ', '').lower(), amount=40)
            for media in medias:
                if media.user and media.user.username:
                    users.add(media.user.username.lower())
                if len(users) >= 25:
                    break
        except Exception as e:
            print(f'[ig_bridge] Hashtag search failed: {e}', file=sys.stderr)
        
        # Fallback: Direct user search
        if len(users) < 10:
            try:
                print(f'[ig_bridge] User search: {keyword}', file=sys.stderr)
                search_results = cl.user_search(keyword)
                for user in search_results[:20]:
                    if user.username:
                        users.add(user.username.lower())
            except Exception as e:
                print(f'[ig_bridge] User search failed: {e}', file=sys.stderr)
        
        print(f'[ig_bridge] Found {len(users)} users', file=sys.stderr)
        json_response(True, users=list(users), count=len(users))
    
    except Exception as e:
        json_error(str(e), reason=classify_error(e), users=[])

def cmd_send_dm(username, password, to_username, message, image_b64, session_dir):
    """Send DM to user"""
    try:
        print(f'[ig_bridge] Sending DM from @{username} to @{to_username}', file=sys.stderr)
        
        # Create and login
        cl = Client()
        cl.login(username, password)
        
        # Get recipient user ID
        try:
            print(f'[ig_bridge] Looking up @{to_username}', file=sys.stderr)
            recipient = cl.user_info_by_username(to_username.lower())
            user_id = recipient.pk
            print(f'[ig_bridge] Found @{to_username} (ID: {user_id})', file=sys.stderr)
        except UserNotFound:
            json_error(f'User @{to_username} not found', reason='user_not_found')
        except Exception as e:
            json_error(f'User lookup failed: {e}', reason='user_not_found')
        
        # Send image if provided
        if image_b64 and image_b64.strip():
            try:
                print(f'[ig_bridge] Sending image', file=sys.stderr)
                import base64
                img_data = base64.b64decode(image_b64)
                # Save temp file
                temp_path = Path('/tmp') / f'insta_msg_{int(__import__("time").time())}.jpg'
                temp_path.write_bytes(img_data)
                # Send
                cl.direct_send_photo(user_ids=[user_id], photo_path=str(temp_path))
                temp_path.unlink()
                print(f'[ig_bridge] Image sent', file=sys.stderr)
            except Exception as e:
                print(f'[ig_bridge] Image send failed: {e}', file=sys.stderr)
        
        # Send text message
        if message:
            print(f'[ig_bridge] Sending text message', file=sys.stderr)
            cl.direct_send(message, user_ids=[user_id])
            print(f'[ig_bridge] Message sent', file=sys.stderr)
        
        json_response(True, to_username=to_username.lower(), message_sent=True)
    
    except Exception as e:
        json_error(str(e), reason=classify_error(e))

def cmd_inbox(username, password, session_dir):
    """Check inbox"""
    try:
        print(f'[ig_bridge] Checking inbox for @{username}', file=sys.stderr)
        
        # Create and login
        cl = Client()
        cl.login(username, password)
        
        messages = []
        
        # Get direct threads
        try:
            threads = cl.direct_threads(amount=20)
            for thread in threads:
                if not thread.users:
                    continue
                other = thread.users[0]
                
                # Get messages from other user
                for msg in (thread.messages or [])[-10:]:
                    if msg.user_id != cl.user_id and msg.text:
                        messages.append({
                            'from_username': other.username.lower(),
                            'text': msg.text,
                            'timestamp': str(msg.timestamp),
                        })
        except Exception as e:
            print(f'[ig_bridge] Inbox fetch failed: {e}', file=sys.stderr)
        
        print(f'[ig_bridge] Found {len(messages)} messages', file=sys.stderr)
        json_response(True, messages=messages, message_count=len(messages))
    
    except Exception as e:
        json_error(str(e), reason=classify_error(e), messages=[])

def main():
    if len(sys.argv) < 3:
        json_error('Invalid arguments', reason='invalid_args')
    
    cmd = sys.argv[1]
    
    try:
        if cmd == 'login' and len(sys.argv) >= 5:
            cmd_login(sys.argv[2], sys.argv[3], sys.argv[4])
        
        elif cmd == 'search' and len(sys.argv) >= 6:
            cmd_search(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5])
        
        elif cmd == 'send_dm' and len(sys.argv) >= 7:
            cmd_send_dm(
                sys.argv[2],  # username
                sys.argv[3],  # password
                sys.argv[4],  # to_username
                sys.argv[5],  # message
                sys.argv[6],  # image_b64
                sys.argv[7]   # session_dir
            )
        
        elif cmd == 'inbox' and len(sys.argv) >= 5:
            cmd_inbox(sys.argv[2], sys.argv[3], sys.argv[4])
        
        else:
            json_error(f'Unknown command: {cmd}', reason='unknown_command')
    
    except Exception as e:
        json_error(str(e), reason='unknown_error')

if __name__ == '__main__':
    main()