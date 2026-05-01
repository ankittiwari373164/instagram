/**
 * lib/ig_client.js — Pure Node.js Instagram bridge (HOSTINGER FIXED)
 * Uses instagram-private-api with proper device fingerprinting, delays, and proxy support
 */

const { IgApiClient, IgCheckpointError, IgLoginRequiredError } = require('instagram-private-api');
const fs   = require('fs');
const path = require('path');
const os   = require('os');

const IS_VERCEL   = !!(process.env.VERCEL || process.env.VERCEL_ENV);
const SESSION_DIR = IS_VERCEL
  ? path.join(os.tmpdir(), 'ig_sessions')
  : path.join(process.cwd(), 'data', 'sessions');

// ── Proxy configuration (for Hostinger) ─────────────────────────
const PROXY_URL = process.env.IG_PROXY || '';  // Set in .env if needed
const USE_DELAY = true;  // Always use delays on Hostinger

function sessionFile(username) {
  if (!fs.existsSync(SESSION_DIR)) {
    try { fs.mkdirSync(SESSION_DIR, { recursive: true }); } catch {}
  }
  return path.join(SESSION_DIR, `${username}.json`);
}

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }
function jitter(min, max) { return min + Math.random() * (max - min); }

// ── Device fingerprinting (prevents Instagram detection) ─────────
const DEVICE_PRESETS = [
  {
    manufacturer: 'samsung',
    model: 'SM-G991B',
    deviceString: 'beyond2',
    androidVersion: '12',
    androidRelease: '12',
  },
  {
    manufacturer: 'google',
    model: 'Pixel 6',
    deviceString: 'raven',
    androidVersion: '12',
    androidRelease: '12',
  },
  {
    manufacturer: 'samsung',
    model: 'SM-G973F',
    deviceString: 'starlte',
    androidVersion: '11',
    androidRelease: '11',
  },
];

const USER_AGENTS = [
  'Instagram 200.0.0.0.1 Android 12/S (api 31; dpi 420) [en_US]',
  'Instagram 202.0.0.0.3 Android 12/S (api 31; dpi 420) [en_US]',
  'Instagram 201.0.0.0.2 Android 11/RP1A (api 30; dpi 420) [en_US]',
];

function getRandomDevice() {
  return DEVICE_PRESETS[Math.floor(Math.random() * DEVICE_PRESETS.length)];
}

function getRandomUserAgent() {
  return USER_AGENTS[Math.floor(Math.random() * USER_AGENTS.length)];
}

// ── Session persistence helpers ───────────────────────────────────
function saveSession(username, ig) {
  try {
    const state = ig.state.serialize();
    // Only save essential state
    delete state.constants;
    fs.writeFileSync(sessionFile(username), JSON.stringify(state, null, 2));
  } catch (e) {
    console.warn(`[ig_client] Failed to save session for ${username}:`, e.message);
  }
}

async function loadSession(username, ig) {
  const sf = sessionFile(username);
  if (!fs.existsSync(sf)) return false;
  try {
    const state = JSON.parse(fs.readFileSync(sf, 'utf8'));
    ig.state.deserialize(state);
    return true;
  } catch (e) {
    console.warn(`[ig_client] Failed to load session for ${username}:`, e.message);
    return false;
  }
}

// ── Classify errors ───────────────────────────────────────────────
function classifyError(e) {
  const msg = (e.message || String(e)).toLowerCase();
  
  // Challenge = 2FA or unusual login
  if (msg.includes('challenge') || msg.includes('checkpoint')) {
    return 'session_expired';
  }
  
  // Rate limiting
  if (msg.includes('rate') || msg.includes('429') || msg.includes('throttle') || msg.includes('try again')) {
    return 'rate_limited';
  }
  
  // Invalid password
  if (msg.includes('invalid') || msg.includes('password') || msg.includes('credentials') || msg.includes('400 bad request')) {
    return 'login_failed';
  }
  
  // User not found
  if (msg.includes('not found') || msg.includes('user_not_found')) {
    return 'user_not_found';
  }
  
  // Blocked
  if (msg.includes('block') || msg.includes('restricted')) {
    return 'blocked';
  }
  
  // Spam detection
  if (msg.includes('spam') || msg.includes('action_blocked')) {
    return 'spam_detected';
  }
  
  return 'unknown';
}

// ── Build a logged-in client ──────────────────────────────────────
async function getClient(username, password) {
  const ig = new IgApiClient();
  
  // 1. Set device with random fingerprint
  const device = getRandomDevice();
  ig.state.generateDevice(username);
  
  // Override with more realistic device
  ig.state.deviceString = device.deviceString;
  ig.state.device.manufacturer = device.manufacturer;
  ig.state.device.model = device.model;
  ig.state.device.deviceString = device.deviceString;
  ig.state.device.hardwareVersion = device.model;
  ig.state.appVersion = '200.0.0.0.1';
  ig.state.userAgent = getRandomUserAgent();
  
  // 2. Set proxy if available (CRITICAL for Hostinger)
  if (PROXY_URL) {
    ig.state.proxyUrl = PROXY_URL;
  }
  
  // 3. Set realistic request delays
  ig.request.end$.subscribe(()=> {
    // Delay between requests
  });
  
  // 4. Try existing session first
  const loaded = await loadSession(username, ig);
  if (loaded) {
    try {
      await sleep(jitter(800, 1500));
      await ig.account.currentUser();
      return ig; // session still valid
    } catch (e) {
      console.warn(`[ig_client] Session expired for ${username}, re-logging in`);
      // Fall through to fresh login
    }
  }

  if (!password) {
    throw new Error(`No password for @${username}`);
  }

  // 5. Fresh login with significant delays
  try {
    console.log(`[ig_client] Attempting login for @${username} with device ${device.model}`);
    
    // Pre-login flow
    await sleep(jitter(1000, 2000));
    await ig.simulate.preLoginFlow();
    
    // Delay before actual login
    await sleep(jitter(2000, 4000));
    
    // LOGIN
    const result = await ig.account.login(username, password);
    
    // Post-login flow
    await sleep(jitter(800, 1500));
    await ig.simulate.postLoginFlow();
    
    // Save session
    saveSession(username, ig);
    
    console.log(`[ig_client] ✓ Login successful for @${username}`);
    return ig;
  } catch (e) {
    const errorMsg = e.message || String(e);
    console.error(`[ig_client] Login failed for @${username}:`, errorMsg);
    
    if (e instanceof IgCheckpointError) {
      throw new Error(`Challenge required for @${username}. Please verify via the Instagram app and try again.`);
    }
    
    const reason = classifyError(e);
    if (reason === 'login_failed') {
      throw new Error(`Invalid credentials for @${username} — check password`);
    }
    
    throw new Error(`Login failed for @${username}: ${errorMsg}`);
  }
}

// ── Commands ──────────────────────────────────────────────────────
async function cmdLogin({ username, password }) {
  try {
    const ig = await getClient(username, password);
    const info = await ig.account.currentUser();
    return {
      ok:             true,
      username,
      user_id:        String(info.pk),
      follower_count: info.follower_count || 0,
    };
  } catch (e) {
    return { 
      ok: false, 
      error: e.message, 
      reason: classifyError(e) 
    };
  }
}

async function cmdSearch({ username, password, keyword }) {
  try {
    const ig = await getClient(username, password);
    const users = new Set();

    // Strategy 1: Hashtag search (most reliable)
    const tags = [
      keyword.replace(/[\s-]/g, '').toLowerCase(),
      keyword.replace(/\s+/g, '_').toLowerCase(),
    ];
    
    for (const tag of tags) {
      try {
        await sleep(jitter(1500, 3000));
        const feed = ig.feed.tag(tag);
        const posts = await feed.items();
        
        for (const p of posts.slice(0, 40)) {
          if (p.user?.username) {
            users.add(p.user.username.toLowerCase());
          }
          if (users.size >= 25) break;
        }
        
        if (users.size >= 25) break;
      } catch (e) {
        console.warn(`[ig_client] Hashtag search failed for "${tag}":`, e.message);
      }
      
      if (users.size >= 25) break;
    }

    // Strategy 2: Direct user search (fallback)
    if (users.size < 10) {
      try {
        await sleep(jitter(1500, 3000));
        const results = await ig.search.users(keyword);
        
        for (const u of results.slice(0, 20)) {
          if (u.username) {
            users.add(u.username.toLowerCase());
          }
        }
      } catch (e) {
        console.warn(`[ig_client] User search failed for "${keyword}":`, e.message);
      }
    }

    saveSession(username, ig);
    return { 
      ok: true, 
      users: [...users].map(u => u.toLowerCase()),
      count: users.size 
    };
  } catch (e) {
    return { 
      ok: false, 
      error: e.message, 
      users: [], 
      reason: classifyError(e) 
    };
  }
}

async function cmdSendDm({ username, password, to_username, message, image_b64, image_ext }) {
  try {
    const ig = await getClient(username, password);

    // Resolve recipient user id
    let userId;
    try {
      await sleep(jitter(1000, 2000));
      const userInfo = await ig.user.searchExact(to_username);
      userId = userInfo.pk;
    } catch (e) {
      return { 
        ok: false, 
        reason: 'user_not_found', 
        error: `User @${to_username} not found` 
      };
    }

    // Send image if provided
    if (image_b64 && image_b64.trim()) {
      try {
        await sleep(jitter(1500, 2500));
        const imgBuf = Buffer.from(image_b64, 'base64');
        await ig.directThread.broadcastPhoto({ 
          userIds: [String(userId)], 
          file: imgBuf 
        });
      } catch (ie) {
        // Log warning but continue with text
        console.warn(`[ig_client] Image send failed for @${to_username}:`, ie.message);
      }
    }

    // Send text message
    if (message) {
      await sleep(jitter(1500, 2500));
      await ig.directThread.broadcastText({ 
        userIds: [String(userId)], 
        text: message 
      });
    }

    saveSession(username, ig);
    return { 
      ok: true, 
      message_sent: true, 
      to_username 
    };
  } catch (e) {
    const reason = classifyError(e);
    if (reason === 'rate_limited') {
      console.warn(`[ig_client] Rate limited for @${username}`);
    }
    return { 
      ok: false, 
      reason, 
      error: e.message 
    };
  }
}

async function cmdInbox({ username, password }) {
  try {
    const ig = await getClient(username, password);
    await sleep(jitter(1500, 2500));
    const feed = ig.feed.directInbox();
    const threads = await feed.items();
    const messages = [];

    for (const thread of threads.slice(0, 20)) {
      const other = thread.users?.[0];
      if (!other) continue;
      
      for (const item of (thread.items || [])) {
        if (String(item.user_id) === String(other.pk) && item.text) {
          messages.push({
            from_username: other.username.toLowerCase(),
            text:          item.text,
            timestamp:     String(item.timestamp),
          });
        }
      }
      
      await sleep(jitter(500, 1200));
    }

    saveSession(username, ig);
    return { 
      ok: true, 
      messages, 
      message_count: messages.length 
    };
  } catch (e) {
    return { 
      ok: false, 
      error: e.message, 
      messages: [], 
      reason: classifyError(e) 
    };
  }
}

async function cmdCheckSession({ username }) {
  const sf = sessionFile(username);
  if (!fs.existsSync(sf)) {
    return { 
      ok: false, 
      valid: false, 
      reason: 'no_session_file' 
    };
  }
  
  try {
    const ig = new IgApiClient();
    ig.state.generateDevice(username);
    const state = JSON.parse(fs.readFileSync(sf, 'utf8'));
    ig.state.deserialize(state);
    await sleep(jitter(800, 1500));
    await ig.account.currentUser();
    return { 
      ok: true, 
      valid: true, 
      username 
    };
  } catch (e) {
    return { 
      ok: false, 
      valid: false, 
      reason: classifyError(e), 
      error: e.message 
    };
  }
}

// ── Dispatch ──────────────────────────────────────────────────────
const COMMANDS = {
  login:         cmdLogin,
  search:        cmdSearch,
  send_dm:       cmdSendDm,
  inbox:         cmdInbox,
  check_session: cmdCheckSession,
};

async function dispatch(payload) {
  const handler = COMMANDS[payload.cmd];
  if (!handler) {
    return { 
      ok: false, 
      error: `Unknown command: ${payload.cmd}` 
    };
  }
  return handler(payload);
}

module.exports = { dispatch };