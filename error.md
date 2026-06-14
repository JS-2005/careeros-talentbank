# WebRTC Connection Diagnostic Report (Update)

This document analyzes the persistent WebRTC connection failure between the Angular frontend and the Python (`aiortc`) backend, even after applying the initial ICE gathering fixes.

---

## 1. The Current State

We previously resolved two critical issues in the backend `webrtc_service.py`:
1. Added Google STUN servers (`stun:stun.l.google.com:19302`).
2. Added a wait loop (`while pc.iceGatheringState != "complete"`) to ensure all ICE candidates are bundled into the SDP answer before sending it back to the client.

However, the `WebRTC ICE State` still transitions from `checking` -> `disconnected`. 
**Why?** Because while the signaling is perfect and the SDPs are being exchanged, the actual UDP peer-to-peer connection is being blocked or cannot be routed.

---

## 2. Root Cause of Persistent ICE Failures on Localhost

When running WebRTC locally on Windows (especially between a browser and a Python process), there are two major culprits that cause ICE to fail:

### Culprit A: mDNS Local IP Masking (The most common cause)
For privacy reasons, modern browsers (Chrome, Edge, Firefox) **hide your real local IP address** in WebRTC candidates. Instead of sending `192.168.1.5` or `127.0.0.1`, the browser generates an mDNS hostname like `a1b2c3d4-xxxx-xxxx.local`.
* **The Problem:** The Python `aiortc` library **does not support mDNS resolution**. When `aiortc` receives `a1b2c3d4.local` from the browser, it silently fails to resolve it to an IP address. 
* **The Result:** Since the local IP cannot be resolved, and the public STUN IP often fails due to your local router lacking "Hairpin NAT" (NAT loopback), the connection has no valid path and fails.

### Culprit B: Windows Firewall Blocking Python UDP
WebRTC uses random, high-range UDP ports (e.g., 40,000–60,000) to stream media and data. 
* **The Problem:** Windows Defender Firewall often blocks incoming UDP traffic to `python.exe` by default. Even if `aiortc` binds correctly, the UDP packets sent from Chrome never reach the Python process.
* **The Result:** The ICE state hangs at `checking` and eventually times out to `disconnected`.

---

## 3. Step-by-Step Fixes for Local Development

To fix this and successfully connect the frontend to the backend locally, you must apply the following workarounds:

### Step 1: Disable mDNS IP Masking in your Browser
Since this is local development, you need to allow Chrome/Edge to expose the real `127.0.0.1` IP to the Python backend.

1. Open a new tab in Chrome or Edge.
2. Navigate to: `chrome://flags/#enable-webrtc-hide-local-ips-with-mdns` (or `edge://flags/...`)
3. Change the dropdown for **Anonymize local IPs exposed by WebRTC** from `Default` to **Disabled**.
4. Click the **Relaunch** button at the bottom right of the browser to restart it.

### Step 2: Allow Python through Windows Firewall
Ensure that your Python executable is allowed to receive UDP traffic.

1. Press the Windows Key, type **Allow an app through Windows Firewall**, and hit Enter.
2. Click **Change settings** (requires administrator privileges).
3. Scroll down and look for **Python** or **python.exe**. 
4. Ensure both the **Private** and **Public** checkboxes are ticked.
5. If Python is not listed, click **Allow another app...**, browse to your python executable (e.g., inside your virtual environment or `C:\Python310\python.exe`), and add it.

### Step 3: Ensure Backend Runs on `0.0.0.0` or `127.0.0.1`
Make sure that your Python backend API (FastAPI/Uvicorn) is running on localhost and that you are accessing the Angular app via `localhost` (not `127.0.0.1` in one and `localhost` in the other, as this can cause CORS or ICE mismatch issues).

---

## 4. Verification Plan

After disabling mDNS in your browser and checking the firewall:
1. Reload the Angular frontend.
2. Enter the meeting room.
3. The `WebRTC ICE State` should now successfully transition from `checking` to `connected`.
4. The DataChannel will open, and the AI Interview session will begin.

*(Note: For a production deployment, these local workarounds are not needed because the Python backend will be hosted on a public server, and you would deploy a **TURN server** (like Coturn) to guarantee connection traversal across restrictive networks).*
