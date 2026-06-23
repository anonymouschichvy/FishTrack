#!/usr/bin/env python3
"""
FishTrack Analytics & Prediction Engine (Refined & Data-Driven)
Integrates ACTUAL buoy telemetry files on disk with the BFAR MIMAROPA fish database.
Bridges YOLO species classifications with BFAR local common names.
"""

import os
import re
import math
import json
import glob
import logging
import hashlib
from datetime import datetime, date
from pathlib import Path

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("FishTrackAnalytics")

ANALYTICS_AVAILABLE = True

# Define base paths
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
ANALYTICS_DIR = DATA_DIR / "analytics"
PREDICTIONS_DIR = ANALYTICS_DIR / "predictions"
DAILY_SUMMARIES_DIR = ANALYTICS_DIR / "daily_summaries"
TIMELINE_SUMMARIES_DIR = ANALYTICS_DIR / "timeline_summaries"
SPECIES_JSON_PATH = DATA_DIR / "species_commodity.json"

# BFAR Official MIMAROPA Authority Citation
BFAR_CITATION = (
    "Republic of the Philippines, Department of Agriculture, "
    "Bureau of Fisheries and Aquatic Resources (BFAR) Regional Fisheries Office - MIMAROPA, "
    "Provincial Fishery Office, Boac, Marinduque. Noted by: Joel G. Malabana, OIC, PFO."
)

# Ensure directories exist
for d in [ANALYTICS_DIR, PREDICTIONS_DIR, DAILY_SUMMARIES_DIR, TIMELINE_SUMMARIES_DIR]:
    d.mkdir(parents=True, exist_ok=True)


# ===== GEMINI AI API INTEGRATION =====
import requests
from typing import Optional

AI_YOLO_TO_BFAR_CACHE = {}

def query_gemini_api(prompt: str) -> Optional[str]:
    key = "API"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={key}"
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [{
            "parts": [{
                "text": prompt
            }]
        }]
    }
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=25)
        if response.status_code == 200:
            res_json = response.json()
            text = res_json["candidates"][0]["content"]["parts"][0]["text"]
            return text.strip()
        else:
            logger.error(f"Gemini API error {response.status_code}: {response.text}")
            return None
    except Exception as e:
        logger.error(f"Error querying Gemini API: {e}")
        return None

def ai_verify_yolo_to_bfar(yolo_species: str, species_list: list) -> Optional[str]:
    """
    Queries Gemini API to verify and map captured YOLO species to the closest connected family/species
    in the BFAR official species list. Caches the result in AI_YOLO_TO_BFAR_CACHE.
    """
    if not yolo_species:
        return None
        
    # Check memory cache first to avoid redundant API calls
    if yolo_species in AI_YOLO_TO_BFAR_CACHE:
        return AI_YOLO_TO_BFAR_CACHE[yolo_species]
        
    # Check standard static map as first fallback
    if yolo_species in YOLO_TO_BFAR_MAP:
        return YOLO_TO_BFAR_MAP[yolo_species]

    logger.info(f"Querying Gemini AI to verify yolo species '{yolo_species}' against BFAR taxonomy...")
    
    bfar_list_str = "\n".join([f"- Scientific: {f['scientific_name']}, Common: {f['common_name']}" for f in species_list])
    
    prompt = f"""
You are an expert marine biologist verifying fish species taxonomy for the Bureau of Fisheries and Aquatic Resources (BFAR) MIMAROPA, Philippines.
A computer vision model (YOLO) detected the fish species: "{yolo_species}".
We need to verify and map this scientific classification to the closest biologically connected family or species in the official BFAR list below.

Official BFAR List:
{bfar_list_str}

Task:
1. Identify the family, genus, or species of the captured fish "{yolo_species}".
2. Determine if it belongs to or is closely connected to any species in the BFAR list (e.g. they share the same genus, family, or represent the same local common name category).
3. If it is connected, output ONLY the exact "Common Name" (e.g., "Yellowfin Tuna (Tambakol)" or "Tilapia") of the matching BFAR species from the list. Do not write any other text, explanations, markdown, or symbols.
4. If there is no biological connection, output "None".

Connected BFAR Common Name:"""

    mapped_name = query_gemini_api(prompt)
    if mapped_name and mapped_name != "None" and any(f["common_name"].lower() == mapped_name.lower() or f["common_name"].lower() in mapped_name.lower() for f in species_list):
        # Match case with official list
        matched_official = next((f["common_name"] for f in species_list if f["common_name"].lower() == mapped_name.lower() or f["common_name"].lower() in mapped_name.lower()), mapped_name)
        AI_YOLO_TO_BFAR_CACHE[yolo_species] = matched_official
        logger.info(f"✅ AI verification successful: mapped '{yolo_species}' to BFAR '{matched_official}'")
        return matched_official
    else:
        AI_YOLO_TO_BFAR_CACHE[yolo_species] = None
        logger.info(f"❌ AI verification: no connected BFAR family found for '{yolo_species}'")
        return None

def ai_generate_predictive_insights(buoy_name, env_data, predictions):
    """
    Generates a 3-paragraph summary using Gemini API based on telemetry parameters
    and calculated predictions.
    """
    # Prepare top predictions
    top_preds = predictions[:5]
    preds_str = "\n".join([f"- {p['common_name']} ({p['scientific_name']}): {p['probability']}% probability, confidence: {p['confidence']}" for p in top_preds])
    
    # Check if buoy has data
    if not env_data.get("has_data", True):
        prompt = f"""
You are an expert marine biologist analyzing telemetry for FishTrack.
Buoy {buoy_name} is currently OFFLINE on {env_data['timestamp'][:10]}. No telemetry logs are available.
Please write a short, professional analysis stating that the hardware is offline, and explain what seasonal predictions (based on the BFAR MIMAROPA database) suggest for this sector at this time of year (Month: {datetime.strptime(env_data['timestamp'][:10], '%Y-%m-%d').strftime('%B')}).
Keep the explanation under 150 words in clean HTML paragraphs (<p>). Do not include any other markdown formatting blocks.
"""
    else:
        prompt = f"""
You are an expert marine biologist and predictive modeller for FishTrack, collaborating with the Bureau of Fisheries and Aquatic Resources (BFAR) MIMAROPA.
Write a detailed AI predictive analysis for buoy "{buoy_name}" located at coordinates {env_data['latitude']:.4f}°, {env_data['longitude']:.4f}° ({env_data['location_desc']}, {env_data['water_body']} zone).

Current telemetry on date {env_data['timestamp'][:10]}:
- GPS Status: {env_data['fix_quality']} with {env_data['num_satellites']} satellites.
- Battery Health: {env_data['battery_percent']}% level ({env_data['battery_voltage_v']}V) in state "{env_data['battery_charge_state']}".
- YOLO Camera Detections: {env_data['camera_processed_frames']} frames processed.
- Sonar Scans: {env_data['sonar_total_scans']} scans with {env_data['sonar_detections_count']} biomass targets.

Calculated top fish species presence probabilities:
{preds_str}

Task:
Write a 3-paragraph summary in clean HTML format (using <p> tags):
1. Paragraph 1: Analyze the current hardware status, telemetry validity, and coordinate positioning.
2. Paragraph 2: Correlate the seasonal migration and availability period from the BFAR database for this month.
3. Paragraph 3: Correlate the camera YOLO captures with the acoustic sonar biomass targets to verify the presence of connected family species and summarize the final predictions.

Do not write markdown block quotes (```html), just return the raw HTML string.
"""
    
    logger.info(f"Querying Gemini AI to generate insights for buoy '{buoy_name}'...")
    res = query_gemini_api(prompt)
    if res:
        # Strip any markdown formatting block quotes if the model outputted them
        res = res.replace("```html", "").replace("```", "").strip()
        return res
    else:
        return None

def ai_analyze_presence_probabilities(buoy_name, env_data, species_list, observed_bfar_commons):
    """
    Queries Gemini AI to analyze and return the Species Presence Probability for each BFAR species
    based on environmental telemetry, coordinates, target date month, and observed connected family species.
    """
    if not env_data.get("has_data", True):
        return None
        
    species_list_str = "\n".join([f"- Scientific: {f['scientific_name']}, Common: {f['common_name']}" for f in species_list])
    observed_str = ", ".join(observed_bfar_commons) if observed_bfar_commons else "None"
    
    timestamp_str = env_data.get("timestamp", "")
    try:
        dt = datetime.strptime(timestamp_str[:10], "%Y-%m-%d")
        month_name = dt.strftime("%B")
    except Exception:
        month_name = "February"
        
    prompt = f"""
You are a marine biology predictive AI working with BFAR MIMAROPA, Philippines.
Given the remote telemetry from buoy "{buoy_name}" at coordinates {env_data['latitude']:.4f}°N, {env_data['longitude']:.4f}°E ({env_data['location_desc']}, {env_data['water_body']} zone):
- Date: {timestamp_str[:10]} (Month: {month_name})
- YOLO Camera Frames: {env_data['camera_processed_frames']} processed
- Acoustic Sonar Scans: {env_data['sonar_total_scans']} sweeps with {env_data['sonar_detections_count']} biomass targets
- Captured species (verified by BFAR data): {observed_str}

Evaluate the Species Presence Probability (0.0% to 100.0%) and confidence level ('HIGH', 'MEDIUM', 'LOW', or 'HIGH (Seen)') for each of the official BFAR species in the list below.

Rules for evaluation:
1. Direct Sightings: If a species is in the captured species list, its probability must be 98.0% and confidence must be 'HIGH (Seen)'.
2. Connected Family Species: If a captured species is biologically connected to another species in the list (e.g. they belong to the same family or genus, like Tunas: Bullet/Frigate/Skipjack/Yellowfin Tuna; or Scads: Round/Redtail/Bigeye Scad; or Mackerels: Short/Indian/Spanish Mackerel; or Sardines; or Snappers; or Groupers; or Tilapia), elevate the probability and confidence of that connected species.
3. Environmental and Habitat compatibility:
   - Offshore/Deep species (e.g. Swordfish, Bullet Tuna, Frigate Tuna, Skipjack Tuna, Yellowfin Tuna, Dolphin Fish, Moon Fish) should have higher probability/confidence in 'Offshore Deep' or 'Marine Pass' zones.
   - Coastal/Reef species (e.g. Round Scad, Short Mackerel, Snapper, Grouper, Parrot Fish) should have higher probability/confidence in 'Coastal Shelf' or 'Marine Pass' zones.
4. Seasonality: Check if the current month ({month_name}) matches the availability period of the species in the official BFAR list. If it does, elevate its score.

Official BFAR Species List to evaluate:
{species_list_str}

Please return the results as a raw JSON object ONLY. Do not wrap the JSON in markdown code blocks or write any introductory/concluding text.
Format of the JSON object:
{{
  "scientific_name_here": {{
    "probability": float (0.0 to 100.0),
    "confidence": "HIGH" | "MEDIUM" | "LOW" | "HIGH (Seen)",
    "matches": ["list of match factor strings"],
    "mismatches": ["list of limiting factor strings"]
  }},
  ...
}}
"""
    logger.info(f"Querying Gemini AI to calculate species presence probabilities for buoy '{buoy_name}'...")
    res = query_gemini_api(prompt)
    if res:
        try:
            res_clean = res.replace("```json", "").replace("```", "").strip()
            start_idx = res_clean.find('{')
            end_idx = res_clean.rfind('}')
            if start_idx != -1 and end_idx != -1:
                res_clean = res_clean[start_idx:end_idx+1]
            return json.loads(res_clean)
        except Exception as e:
            logger.error(f"Error parsing Gemini JSON response for species presence probability: {e}")
            return None
    return None



# ===== 1. SPECIES JSON LOADER =====

def load_species_from_json(json_path=SPECIES_JSON_PATH):
    """
    Loads the fish species list from data/species_commodity.json.
    This is the single authoritative source for all species used in predictions.
    To add new species, edit that JSON file — no code changes needed.
    Returns a list of dicts with scientific_name, common_name, availability, municipalities.
    """
    if not os.path.exists(json_path):
        logger.warning(f"Species JSON not found at {json_path}. Falling back to embedded defaults.")
        return _get_embedded_species_fallback()

    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        species = data.get("species", [])
        if not species:
            logger.warning("Species JSON has no entries. Falling back to embedded defaults.")
            return _get_embedded_species_fallback()
        logger.info(f"Loaded {len(species)} species from {json_path}")
        return species
    except Exception as e:
        logger.error(f"Error loading species JSON: {e}. Falling back to embedded defaults.")
        return _get_embedded_species_fallback()


def _get_embedded_species_fallback():
    """Minimal emergency fallback used only when species_commodity.json is missing or corrupt."""
    return [
        {"scientific_name": "Decapterus macrosoma",   "common_name": "Swordfish",                 "availability": "March–May",   "municipalities": "Less common; found in deeper offshore waters"},
        {"scientific_name": "Lampris guttatus",        "common_name": "Bullet Tuna",               "availability": "Year-round",  "municipalities": "Found in various coastal areas"},
        {"scientific_name": "Carangoides oblongus",    "common_name": "Frigate Tuna (Tulingan)",    "availability": "Year-round",  "municipalities": "Common in coastal waters"},
        {"scientific_name": "Stolephorus spp.",        "common_name": "Yellowfin Tuna (Tambakol)",  "availability": "Year-round",  "municipalities": "Found in various coastal areas"},
        {"scientific_name": "Katsuwonus pelamis",      "common_name": "Indian Mackerel (Bangus)",   "availability": "Year-round",  "municipalities": "Common in coastal waters"},
        {"scientific_name": "Coryphaena hippurus",     "common_name": "Round Scad (Galunggong)",    "availability": "Year-round",  "municipalities": "Very common in coastal waters"},
        {"scientific_name": "Rastrelliger brachysoma", "common_name": "Moon Fish (Opah)",           "availability": "April–June",  "municipalities": "Rare; found in deeper offshore waters"},
        {"scientific_name": "Caesio cuning",           "common_name": "Oblong Trevally",            "availability": "March–May",   "municipalities": "Less common; found in coastal areas"},
        {"scientific_name": "Scomberomorus commerson", "common_name": "Skipjack Tuna (Gulyasan)",   "availability": "Year-round",  "municipalities": "Very common in coastal waters"},
        {"scientific_name": "Lutjanus spp.",           "common_name": "Fusilier (Dalagang Bukid)",  "availability": "March–May",   "municipalities": "Less common; found in coastal areas"},
        {"scientific_name": "Selar crumenophthalmus",  "common_name": "Snapper (Maya-maya)",        "availability": "Year-round",  "municipalities": "Common in coastal waters"},
        {"scientific_name": "Nemipterus spp.",         "common_name": "Bigeye Scad (Matangbaka)",   "availability": "Year-round",  "municipalities": "Common in coastal waters"},
    ]


# ===== 2. SPECIES KNOWLEDGE CENTER PROFILES DATABASE =====

SPECIES_PROFILES_PATH = DATA_DIR / "species_profiles.json"


def _load_species_profiles(json_path=SPECIES_PROFILES_PATH):
    """
    Loads species biological profiles from data/species_profiles.json.
    Keys in the JSON are 'scientific_name|common_name'.
    Returns (profiles_dict, default_profile).
    """
    try:
        if os.path.exists(json_path):
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            profiles = data.get("profiles", {})
            default = data.get("default_profile", {})
            logger.info(f"Loaded {len(profiles)} species profiles from {json_path}")
            return profiles, default
    except Exception as e:
        logger.error(f"Error loading species profiles JSON: {e}. Using empty profiles.")
    return {}, {
        "depth_range": "5 - 50m", "size_weight": "Avg 20-40 cm, 300g-1.5kg",
        "habitat": "Coastal waters and reef structures",
        "feeding": "Omnivorous, feeding on zooplankton and algae",
        "breeding": "Spawns during seasonal transitions", "conservation": "Least Concern",
        "importance": "Supports small-scale coastal artisanal fisheries and local food markets."
    }


SPECIES_PROFILES, DEFAULT_PROFILE = _load_species_profiles()


def get_fish_profile(scientific_name, common_name):
    """Retrieves full profile for a species, falling back to a template if not fully mapped."""
    exact_key = f"{scientific_name}|{common_name}"
    if exact_key in SPECIES_PROFILES:
        profile = SPECIES_PROFILES[exact_key].copy()
    else:
        profile = DEFAULT_PROFILE.copy()
        # Partial match: scientific name or common name
        for key, val in SPECIES_PROFILES.items():
            parts = key.split("|", 1)
            if len(parts) == 2 and (parts[0] == scientific_name or parts[1] == common_name):
                profile = val.copy()
                break

    # Attach identity and authoritative citation
    profile["scientific_name"] = scientific_name
    profile["common_name"] = common_name
    profile["citation"] = BFAR_CITATION
    return profile


# ===== 3. BRIDGING YOLO DETECTIONS TO BFAR TAXONOMY =====

YOLO_BRIDGE_PATH = DATA_DIR / "yolo_bfar_bridge.json"


def _load_yolo_bfar_map(json_path=YOLO_BRIDGE_PATH):
    """
    Loads the YOLO scientific name → BFAR common name bridge from data/yolo_bfar_bridge.json.
    Keys starting with 'comment_' are documentation-only and are automatically skipped.
    To add new YOLO labels, edit that JSON file — no code changes needed.
    """
    try:
        if os.path.exists(json_path):
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            raw = data.get("mappings", {})
            # Filter out comment/documentation keys
            bridge = {k: v for k, v in raw.items() if not k.startswith("comment_")}
            logger.info(f"Loaded {len(bridge)} YOLO→BFAR mappings from {json_path}")
            return bridge
    except Exception as e:
        logger.error(f"Error loading YOLO bridge JSON: {e}. Using empty map.")
    return {}


# Maps YOLO scientific labels → BFAR Marinduque common names
YOLO_TO_BFAR_MAP = _load_yolo_bfar_map()


def calculate_match_score(fish, env_data, hist_boost):
    """
    Calculates compatibility score between a fish species and environmental parameters.
    Returns: (score, matches, mismatches)
    """
    matches = []
    mismatches = []
    
    # 1. Seasonality check
    timestamp_str = env_data.get("timestamp", "")
    try:
        dt = datetime.strptime(timestamp_str[:10], "%Y-%m-%d")
        month_num = dt.month
        month_name = dt.strftime("%B")
    except Exception:
        dt = datetime.utcnow()
        month_num = dt.month
        month_name = dt.strftime("%B")
        
    avail = fish.get("availability", "Year-round")
    season_match = False
    
    if avail == "Year-round":
        season_match = True
        matches.append("Date falls in availability window (Year-round)")
    else:
        months_map = {
            "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
            "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
            "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12
        }
        found_months = re.findall(r'[a-zA-Z]+', avail)
        if len(found_months) >= 2:
            m1_name = found_months[0].lower()
            m2_name = found_months[1].lower()
            if m1_name in months_map and m2_name in months_map:
                m1 = months_map[m1_name]
                m2 = months_map[m2_name]
                if m1 <= m2:
                    if m1 <= month_num <= m2:
                        season_match = True
                else:
                    if month_num >= m1 or month_num <= m2:
                        season_match = True
        
        if season_match:
            matches.append(f"Date falls in seasonal window ({avail})")
        else:
            mismatches.append(f"Target month ({month_name}) is outside typical seasonal window ({avail})")
            
    # 2. Habitat compatibility
    water_body = env_data.get("water_body", "Coastal Shelf")
    municipalities = fish.get("municipalities", "").lower()
    
    location_match = False
    if "offshore" in municipalities or "deeper" in municipalities:
        if water_body in ["Offshore Deep", "Marine Pass"]:
            location_match = True
            matches.append(f"Proximity match: Deeper preference matches {water_body} zone")
        else:
            mismatches.append(f"Depth mismatch: Prefers deeper offshore, buoy in {water_body}")
    elif "coastal" in municipalities or "various" in municipalities or "common" in municipalities:
        if water_body in ["Coastal Shelf", "Marine Pass"]:
            location_match = True
            matches.append(f"Proximity match: Coastal preference matches {water_body} zone")
        else:
            mismatches.append(f"Zone mismatch: Prefers coastal shelves, buoy in {water_body}")
    else:
        location_match = True
        matches.append("Habitat compatibility: General marine distribution")

    # 3. Sonar echoes correlation
    sonar_dets = env_data.get("sonar_detections_count", 0)
    common_name = fish.get("common_name", "").lower()
    is_schooling = any(term in common_name for term in ["tuna", "sardinella", "mackerel", "anchov", "scad", "herring"])
    
    if sonar_dets > 5 and is_schooling:
        matches.append("Sonar Biomass: High acoustic echoes match schooling pelagic patterns")
        
    # Calculate score
    base_score = 0.5
    if season_match:
        base_score += 0.25
    if location_match:
        base_score += 0.25
        
    if hist_boost > 0:
        base_score = 1.0
    elif sonar_dets > 5 and is_schooling:
        base_score = min(0.95, base_score + 0.1)
        
    score = max(0.1, min(1.0, base_score))
    return score, matches, mismatches


# ===== 4. DATABASE OF ACTUAL TELEMETRY RECORDS =====

DEFAULT_BUOY_METADATA = {
    "BUOY-POSEIDON": {
        "lat": 13.435,
        "lon": 121.890,
        "location_desc": "Central Marinduque Pass",
        "water_body": "Marine Pass",
        "max_depth_m": 60,
    }
}


class TelemetryDatabase:
    """Loads and indexes telemetry data directly from files on disk."""
    def __init__(self):
        self.gps_records = {}       # (buoy, date_str) -> dict
        self.battery_records = {}   # (buoy, date_str) -> dict
        self.fish_records = {}      # (buoy, date_str) -> list
        self.sonar_records = {}     # (buoy, date_str) -> list
        self.buoy_registry = {}     # buoy_name -> metadata dict
        self.load_all_records()

    def load_all_records(self):
        from config import RECEIVED_DATA_DIR, FISH_DATA_DIR, SONAR_DATA_DIR, GPS_DATA_DIR, BATTERY_DATA_DIR
        
        # 1. Load GPS
        if GPS_DATA_DIR.exists():
            for f in GPS_DATA_DIR.glob("*.json"):
                try:
                    with open(f, 'r', errors='ignore') as fh:
                        data = json.load(fh)
                        if isinstance(data, dict):
                            name = f.name
                            parts = name.split("_")
                            buoy = parts[0]
                            rec_utc = data.get("recorded_at_utc")
                            if rec_utc and len(rec_utc) >= 10:
                                ds_formatted = rec_utc[:10]
                            else:
                                ds = parts[1] if len(parts) > 1 else ""
                                ds_formatted = f"{ds[:4]}-{ds[4:6]}-{ds[6:]}" if len(ds) == 8 else ""
                            if ds_formatted:
                                self.gps_records[(buoy, ds_formatted)] = data
                except Exception as e:
                    logger.debug(f"Error loading GPS file: {e}")

        # 2. Load Battery
        if BATTERY_DATA_DIR.exists():
            for f in BATTERY_DATA_DIR.glob("*.json"):
                try:
                    with open(f, 'r', errors='ignore') as fh:
                        data = json.load(fh)
                        if isinstance(data, dict):
                            name = f.name
                            parts = name.split("_")
                            buoy = parts[0]
                            ds = parts[1] if len(parts) > 1 else ""
                            if len(ds) == 8:
                                ds_formatted = f"{ds[:4]}-{ds[4:6]}-{ds[6:]}"
                                self.battery_records[(buoy, ds_formatted)] = data
                except Exception as e:
                    pass

        # 3. Load Fish Detections
        if FISH_DATA_DIR.exists():
            for f in FISH_DATA_DIR.glob("*.json"):
                try:
                    with open(f, 'r', errors='ignore') as fh:
                        data = json.load(fh)
                        name = f.name
                        parts = name.split("_")
                        buoy = parts[0]
                        
                        # Records have a "Timestamp" like "19/02/2026 19:55"
                        if isinstance(data, list):
                            for rec in data:
                                ts = rec.get("Timestamp")
                                if ts:
                                    try:
                                        dt = datetime.strptime(ts, "%d/%m/%Y %H:%M")
                                        rec_date = dt.strftime("%Y-%m-%d")
                                        key = (buoy, rec_date)
                                        if key not in self.fish_records:
                                            self.fish_records[key] = []
                                        self.fish_records[key].append(rec)
                                    except Exception as e:
                                        pass
                except Exception as e:
                    pass

        # 4. Load Sonar scans
        if SONAR_DATA_DIR.exists():
            for f in SONAR_DATA_DIR.glob("*.json"):
                try:
                    with open(f, 'r', errors='ignore') as fh:
                        data = json.load(fh)
                        name = f.name
                        parts = name.split("_")
                        buoy = parts[0]
                        
                        # Records have an "Image Name" like "17_02_2026_08_23_00.png"
                        if isinstance(data, list):
                            for rec in data:
                                img = rec.get("Image Name")
                                if img:
                                    m = re.match(r'(\d+)_(\d+)_(\d+)', img)
                                    if m:
                                        rec_date = f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
                                        key = (buoy, rec_date)
                                        if key not in self.sonar_records:
                                            self.sonar_records[key] = []
                                        self.sonar_records[key].append(rec)
                except Exception as e:
                    pass
        
        logger.info(f"Loaded {len(self.gps_records)} GPS, {len(self.battery_records)} battery, {len(self.fish_records)} fish dates, and {len(self.sonar_records)} sonar dates from disk.")
        self.build_buoy_registry()

    def build_buoy_registry(self):
        """
        Discovers active buoy nodes dynamically based on files loaded on disk
        and ACTIVE_BUOY_LIST in config.py. Sets coordinates from GPS records if available.
        """
        # Discover all unique buoy names from loaded records
        buoy_names = set()
        for k in list(self.gps_records.keys()) + list(self.battery_records.keys()) + list(self.fish_records.keys()) + list(self.sonar_records.keys()):
            buoy_names.add(k[0])
            
        # Also check ACTIVE_BUOY_LIST from config
        from config import ACTIVE_BUOY_LIST
        for b in ACTIVE_BUOY_LIST:
            buoy_names.add(b)
            
        # Build registry entries dynamically
        self.buoy_registry = {}
        for name in buoy_names:
            if name in DEFAULT_BUOY_METADATA:
                meta = DEFAULT_BUOY_METADATA[name].copy()
            else:
                meta = {
                    "lat": 13.400, "lon": 121.900,  # Default center coordinates
                    "location_desc": f"{name} Station",
                    "water_body": "Coastal Shelf",
                    "max_depth_m": 50
                }
            
            # Try to get actual coordinates from GPS records for this buoy
            buoy_gps = [v for k, v in self.gps_records.items() if k[0] == name]
            if buoy_gps:
                latest_gps = buoy_gps[-1]
                if isinstance(latest_gps, dict) and "latitude" in latest_gps and "longitude" in latest_gps:
                    meta["lat"] = latest_gps["latitude"]
                    meta["lon"] = latest_gps["longitude"]
                    
            self.buoy_registry[name] = meta
            
        logger.info(f"Dynamically registered {len(self.buoy_registry)} buoys from files: {list(self.buoy_registry.keys())}")

    def query_buoy_telemetry(self, buoy_name, target_date_str):
        """
        Queries actual telemetry records from database.
        Resolves the closest available date for each sensor type independently if needed.
        """
        # Determine coordinate information from registry first
        buoy_reg = self.buoy_registry.get(buoy_name)
        if not buoy_reg:
            buoy_reg = DEFAULT_BUOY_METADATA.get(buoy_name, DEFAULT_BUOY_METADATA["BUOY-POSEIDON"])
        lat = buoy_reg["lat"]
        lon = buoy_reg["lon"]

        gps_dates = [k[1] for k in self.gps_records.keys() if k[0] == buoy_name]
        bat_dates = [k[1] for k in self.battery_records.keys() if k[0] == buoy_name]
        fish_dates = [k[1] for k in self.fish_records.keys() if k[0] == buoy_name]
        sonar_dates = [k[1] for k in self.sonar_records.keys() if k[0] == buoy_name]

        # Check if the target date actually has ANY telemetry files on disk for this buoy
        has_data = (target_date_str in gps_dates) or (target_date_str in bat_dates) or (target_date_str in fish_dates) or (target_date_str in sonar_dates)

        if not has_data:
            return {
                "timestamp": datetime.strptime(target_date_str, "%Y-%m-%d").isoformat() + "Z",
                "latitude": lat,
                "longitude": lon,
                "num_satellites": None,
                "fix_quality": "Offline",
                "altitude_m": 0.0,
                "battery_percent": None,
                "battery_voltage_v": None,
                "battery_charge_state": "Offline",
                "camera_processed_frames": 0,
                "sonar_total_scans": 0,
                "sonar_detections_count": 0,
                "buoy_name": buoy_name,
                "location_desc": buoy_reg["location_desc"],
                "water_body": buoy_reg["water_body"],
                "is_fallback": False,
                "has_data": False,
                "reference_date": None,
                "actual_fish_records": []
            }

        # Otherwise, the buoy HAS data on this date
        target_dt = datetime.strptime(target_date_str, "%Y-%m-%d")

        # 1. Resolve Fish Detections
        if target_date_str in fish_dates:
            selected_fish_date = target_date_str
            fish_is_fallback = False
        else:
            if fish_dates:
                selected_fish_date = min(fish_dates, key=lambda x: abs(datetime.strptime(x, "%Y-%m-%d") - target_dt))
                fish_is_fallback = True
            else:
                selected_fish_date = None
                fish_is_fallback = True

        # 2. Resolve Sonar Detections
        if target_date_str in sonar_dates:
            selected_sonar_date = target_date_str
            sonar_is_fallback = False
        else:
            if sonar_dates:
                selected_sonar_date = min(sonar_dates, key=lambda x: abs(datetime.strptime(x, "%Y-%m-%d") - target_dt))
                sonar_is_fallback = True
            else:
                selected_sonar_date = None
                sonar_is_fallback = True

        # 3. Resolve GPS
        if target_date_str in gps_dates:
            selected_gps_date = target_date_str
            gps_is_fallback = False
        else:
            if gps_dates:
                selected_gps_date = min(gps_dates, key=lambda x: abs(datetime.strptime(x, "%Y-%m-%d") - target_dt))
                gps_is_fallback = True
            else:
                selected_gps_date = None
                gps_is_fallback = True

        # 4. Resolve Battery
        if target_date_str in bat_dates:
            selected_bat_date = target_date_str
            bat_is_fallback = False
        else:
            if bat_dates:
                selected_bat_date = min(bat_dates, key=lambda x: abs(datetime.strptime(x, "%Y-%m-%d") - target_dt))
                bat_is_fallback = True
            else:
                selected_bat_date = None
                bat_is_fallback = True

        # Fetch actual files
        gps_rec = self.gps_records.get((buoy_name, selected_gps_date)) if selected_gps_date else None
        bat_rec = self.battery_records.get((buoy_name, selected_bat_date)) if selected_bat_date else None
        fish_recs = self.fish_records.get((buoy_name, selected_fish_date), []) if selected_fish_date else []
        sonar_recs = self.sonar_records.get((buoy_name, selected_sonar_date), []) if selected_sonar_date else []

        # GPS satellites and quality mapping
        if gps_rec:
            sats = gps_rec.get("num_satellites", 8)
            fix_q = gps_rec.get("fix_quality", 1)
            if fix_q == 1 or fix_q == "1":
                fix_q_str = "GPS Fix (2D)"
            elif fix_q == 2 or fix_q == "2":
                fix_q_str = "DGPS Fix"
            elif fix_q >= 3:
                fix_q_str = "3D Fix"
            else:
                fix_q_str = "No Fix"
            alt = gps_rec.get("altitude_m", 10.0)
        else:
            sats = None
            fix_q_str = "Offline"
            alt = 0.0

        # Battery percentage and voltage mappings
        if bat_rec:
            percent = bat_rec.get("percent", 80)
            if "battery" in bat_rec and isinstance(bat_rec["battery"], dict):
                percent = bat_rec["battery"].get("percent", percent)
            
            voltage = bat_rec.get("voltage_v", 13.32)
            if "voltage_mv" in bat_rec:
                voltage = round(bat_rec["voltage_mv"] / 1000, 2)
            elif "battery" in bat_rec and isinstance(bat_rec["battery"], dict) and "voltage_mv" in bat_rec["battery"]:
                voltage = round(bat_rec["battery"]["voltage_mv"] / 1000, 2)
            charge_s = bat_rec.get("charge_state", "Charging")
        else:
            percent = None
            voltage = None
            charge_s = "Offline"

        # Camera runs
        frames_count = len(fish_recs) if fish_recs else 0

        # Sonar sweeps
        sonar_count = len(sonar_recs) if sonar_recs else 0
        sonar_dets = sum(1 for s in sonar_recs if s.get("Fish Detect", 0) > 0) if sonar_recs else 0

        return {
            "timestamp": datetime.strptime(target_date_str, "%Y-%m-%d").isoformat() + "Z",
            "latitude": lat,
            "longitude": lon,
            "num_satellites": sats,
            "fix_quality": fix_q_str,
            "altitude_m": alt,
            "battery_percent": percent,
            "battery_voltage_v": voltage,
            "battery_charge_state": charge_s,
            "camera_processed_frames": frames_count,
            "sonar_total_scans": sonar_count,
            "sonar_detections_count": sonar_dets,
            "buoy_name": buoy_name,
            "location_desc": buoy_reg["location_desc"],
            "water_body": buoy_reg["water_body"],
            "is_fallback": False,
            "has_data": True,
            "reference_date": None,
            "actual_fish_records": fish_recs
        }


# Initialize static DB
telemetry_db = TelemetryDatabase()


# ===== 5. THE PREDICTION SERVICE CLASS =====

class PredictionService:
    def __init__(self):
        self.species_list = load_species_from_json(SPECIES_JSON_PATH)
        
    def get_species_list(self):
        return self.species_list
        
    def get_detailed_profiles(self):
        return [get_fish_profile(f["scientific_name"], f["common_name"]) for f in self.species_list]
        
    def generate_prediction(self, target_date: date, historical_days=30):
        predictions_by_buoy = {}
        date_str = target_date.strftime("%Y-%m-%d")
        
        for buoy_name in telemetry_db.buoy_registry.keys():
            # Query actual buoy records (or closest fallback date)
            env_data = telemetry_db.query_buoy_telemetry(buoy_name, date_str)
            
            # Analyze actual YOLO detections from files for this date
            actual_yolo_recs = env_data["actual_fish_records"]
            
            # Extract list of actually observed scientific names
            observed_yolo_species = set()
            for rec in actual_yolo_recs:
                for sp in rec.get("Species Detected", []):
                    # Check if confidence threshold is high enough e.g. 50%
                    if sp.get("confidence", 0) >= 0.50:
                        observed_yolo_species.add(sp.get("species"))
            
            # Map observed YOLO species to BFAR common names via AI verification
            observed_bfar_commons = set()
            for yolo_sp in observed_yolo_species:
                mapped_name = ai_verify_yolo_to_bfar(yolo_sp, self.species_list)
                if mapped_name:
                    observed_bfar_commons.add(mapped_name)
            
            # Predict for each fish
            buoy_preds = []
            
            # Query Gemini AI for species presence probability analysis if buoy has data
            ai_probs = None
            if env_data.get("has_data", True):
                ai_probs = ai_analyze_presence_probabilities(buoy_name, env_data, self.species_list, observed_bfar_commons)
                
            for fish in self.species_list:
                sci_name = fish["scientific_name"]
                common_name = fish["common_name"]
                
                # Check if we have AI-generated probabilities for this species
                ai_pred = None
                if ai_probs and isinstance(ai_probs, dict):
                    # Check scientific_name or common_name keys case insensitively
                    for k, v in ai_probs.items():
                        if k.lower() == sci_name.lower() or k.lower() == common_name.lower():
                            if isinstance(v, dict) and "probability" in v:
                                ai_pred = v
                                break
                                
                is_detected_by_yolo = common_name in observed_bfar_commons
                
                if ai_pred:
                    probability = float(ai_pred.get("probability", 10.0))
                    confidence = ai_pred.get("confidence", "LOW")
                    matches = ai_pred.get("matches", [])
                    mismatches = ai_pred.get("mismatches", [])
                    # Ensure direct sightings are marked appropriately
                    if is_detected_by_yolo:
                        confidence = "HIGH (Seen)"
                        probability = 98.0
                        if not any("yolo" in m.lower() or "sighting" in m.lower() for m in matches):
                            matches.insert(0, f"YOLO Sighting: Verified detection in camera log frame!")
                else:
                    # Fallback to rule-based match score
                    hist_boost = 1.0 if is_detected_by_yolo else 0.0
                    score, matches, mismatches = calculate_match_score(fish, env_data, hist_boost)
                    
                    if is_detected_by_yolo:
                        confidence = "HIGH (Seen)"
                        probability = 98.0
                        matches.insert(0, f"YOLO Sighting: Verified detection in camera log frame!")
                    else:
                        probability = round(score * 100, 1)
                        if score >= 0.80:
                            confidence = "HIGH"
                        elif score >= 0.50:
                            confidence = "MEDIUM"
                        else:
                            confidence = "LOW"
                    
                profile = get_fish_profile(sci_name, common_name)
                
                buoy_preds.append({
                    "scientific_name": sci_name,
                    "common_name": common_name,
                    "availability_period": fish["availability"],
                    "location_preference": fish["municipalities"],
                    "probability": probability,
                    "confidence": confidence,
                    "depth_range": profile["depth_range"],
                    "importance": profile["importance"],
                    "citation": profile["citation"],
                    "matches": matches,
                    "mismatches": mismatches,
                    "is_detected": is_detected_by_yolo
                })
                
            # Sort highest probability first
            buoy_preds.sort(key=lambda x: x["probability"], reverse=True)
            
            # Compute indicators
            high_conf_count = sum(1 for p in buoy_preds if p["confidence"].startswith("HIGH"))
            biodiversity_indicator = "Optimal" if high_conf_count >= 8 else ("Moderate" if high_conf_count >= 4 else "Low Activity")
            
            # Recommendations and Alerts
            recommendations = []
            alerts = []
            
            if env_data.get("is_fallback"):
                alerts.append({
                    "type": "info",
                    "title": "Reference Mode Enabled",
                    "message": f"Showing reference telemetry compiled from buoy's nearest logged date ({env_data['reference_date']}) to represent actual hardware data structure."
                })
            
            if env_data["battery_percent"] is not None and env_data["battery_percent"] < 25:
                alerts.append({
                    "type": "warning",
                    "title": "Low Buoy Battery Alert",
                    "message": f"Buoy voltage is low ({env_data['battery_voltage_v']}V, {env_data['battery_percent']}% charge). BMS charging cycle is critical."
                })
            if env_data["num_satellites"] is not None and env_data["num_satellites"] < 8:
                alerts.append({
                    "type": "caution",
                    "title": "GPS Satellite Anomaly",
                    "message": f"Only {env_data['num_satellites']} satellites tracked in coordinate resolution."
                })
                
            # Recommendations
            peak_species = buoy_preds[0]
            recommendations.append(f"Deploy YOLO camera triggers for: {peak_species['common_name']} which has {peak_species['probability']}% presence indicators.")
            recommendations.append(f"Acoustic Correlation: Sonar logs show {env_data['sonar_detections_count']} biomass targets. Match with camera run counts ({env_data['camera_processed_frames']} frames).")
            recommendations.append(f"Verify coordinates: Buoy GPS lock at {env_data['latitude']:.4f}°, {env_data['longitude']:.4f}° fits BFAR municipal distribution: <em>\"{peak_species['location_preference']}\"</em>.")
            
            bat_status = f"{env_data['battery_percent']}%" if env_data['battery_percent'] is not None else "Offline"
            bat_volts = f"{env_data['battery_voltage_v']}V" if env_data['battery_voltage_v'] is not None else "--V"
            recommendations.append(f"Energy Preservation: Monitor charging curves and LiFePO4 cells status ({bat_status} level, {bat_volts}) in state '{env_data['battery_charge_state']}'.")
            
            # Generate AI Insights narrative using Gemini
            ai_analysis = ai_generate_predictive_insights(buoy_name, env_data, buoy_preds)

            predictions_by_buoy[buoy_name] = {
                "buoy_name": buoy_name,
                "location_desc": buoy_info_desc(buoy_name),
                "coordinates": {"lat": env_data["latitude"], "lon": env_data["longitude"]},
                "environmental_conditions": env_data,
                "predictions": buoy_preds,
                "water_quality_status": "Hardware Online" if env_data.get("has_data", True) else "Hardware Offline",
                "biodiversity_indicator": biodiversity_indicator,
                "alerts": alerts,
                "recommendations": recommendations,
                "ai_analysis": ai_analysis,
                "citation": BFAR_CITATION
            }
            
        # Collect all dates with telemetry or detections on disk for any buoy
        all_gps_dates = [k[1] for k in telemetry_db.gps_records.keys()]
        all_bat_dates = [k[1] for k in telemetry_db.battery_records.keys()]
        all_fish_dates = [k[1] for k in telemetry_db.fish_records.keys()]
        all_sonar_dates = [k[1] for k in telemetry_db.sonar_records.keys()]
        
        telemetry_dates = sorted(list(set(all_gps_dates + all_bat_dates)))
        detection_dates = sorted(list(set(all_fish_dates + all_sonar_dates)))

        prediction_payload = {
            "date": date_str,
            "buoys": predictions_by_buoy,
            "verified_telemetry_dates": telemetry_dates,
            "verified_detection_dates": detection_dates,
            "generated_at": datetime.utcnow().isoformat() + "Z"
        }
        
        pred_filepath = PREDICTIONS_DIR / f"prediction_{date_str}.json"
        try:
            with open(pred_filepath, 'w') as f:
                json.dump(prediction_payload, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving prediction log: {e}")
            
        return prediction_payload


# ===== 6. DAILY AGGREGATOR AND TIMELINE SERVICE =====

class DailyAggregator:
    def __init__(self):
        pass
        
    def load_daily_summary(self, target_date: date):
        date_str = target_date.strftime("%Y-%m-%d")
        summary_file = DAILY_SUMMARIES_DIR / f"summary_{date_str}.json"
        if summary_file.exists():
            try:
                with open(summary_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading summary for {date_str}: {e}")
        return None
        
    def create_daily_summary(self, target_date: date):
        date_str = target_date.strftime("%Y-%m-%d")
        
        buoy_data = {}
        total_fish_detected = 0
        
        for name in telemetry_db.buoy_registry.keys():
            env = telemetry_db.query_buoy_telemetry(name, date_str)
            
            # Count actual fish seen in records
            det_count = 0
            for rec in env["actual_fish_records"]:
                det_count += int(rec.get("Fish Detected", 0) or 0)
                
            total_fish_detected += det_count
            
            buoy_data[name] = {
                "environment": env,
                "camera_detections": det_count,
                "sonar_detections": env["sonar_detections_count"]
            }
            
        valid_sats = [d["environment"]["num_satellites"] for d in buoy_data.values() if d["environment"]["num_satellites"] is not None]
        avg_sats = round(sum(valid_sats) / len(valid_sats), 1) if valid_sats else 0.0
        
        valid_battery = [d["environment"]["battery_percent"] for d in buoy_data.values() if d["environment"]["battery_percent"] is not None]
        avg_battery = round(sum(valid_battery) / len(valid_battery), 1) if valid_battery else 0.0
        
        total_frames = sum(d["environment"].get("camera_processed_frames", 0) or 0 for d in buoy_data.values() if d.get("environment"))
        total_scans = sum(d["environment"].get("sonar_total_scans", 0) or 0 for d in buoy_data.values() if d.get("environment"))

        summary_payload = {
            "date": date_str,
            "buoys": buoy_data,
            "total_detections": total_fish_detected,
            "avg_satellites": avg_sats,
            "avg_battery_charge": avg_battery,
            "total_processed_frames": total_frames,
            "total_sonar_scans": total_scans,
            "aggregated_at": datetime.utcnow().isoformat() + "Z"
        }
        
        summary_file = DAILY_SUMMARIES_DIR / f"summary_{date_str}.json"
        try:
            with open(summary_file, 'w') as f:
                json.dump(summary_payload, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving daily summary: {e}")
            
        return summary_payload
        
    def get_or_create_timeline(self, days=30):
        timeline = []
        # Base the timeline around the actual telemetry window (ending Feb 20, 2026)
        # to ensure the historical trend charts show real dynamic data.
        base_date = date(2026, 2, 20)
        from datetime import timedelta
        
        for i in range(days):
            target_dt = base_date - timedelta(days=i)
            summary = self.load_daily_summary(target_dt)
            if not summary:
                summary = self.create_daily_summary(target_dt)
            timeline.append(summary)
            
        timeline.reverse()
        return timeline


# ===== Helper Utilities =====

def buoy_info_desc(buoy_name):
    if buoy_name in telemetry_db.buoy_registry:
        return f"{buoy_name} ({telemetry_db.buoy_registry[buoy_name]['location_desc']})"
    return buoy_name

def run_daily_aggregation(cfg):
    logger.info("Starting scheduled daily data aggregation...")
    aggregator = DailyAggregator()
    today = date.today()
    from datetime import timedelta
    for i in range(14):
        target = today - timedelta(days=i)
        aggregator.create_daily_summary(target)
    logger.info("Daily aggregation complete.")


# Initialize singleton instances
prediction_service = PredictionService()
daily_aggregator = DailyAggregator()

# Standalone execution test
if __name__ == "__main__":
    print("Testing species JSON loading...")
    species = load_species_from_json(SPECIES_JSON_PATH)
    print(f"Loaded {len(species)} species from species_commodity.json")
    
    print("\nTesting actual environmental lookup for today...")
    env = telemetry_db.query_buoy_telemetry("BUOY-POSEIDON", "2026-06-19")
    print(json.dumps({k: v for k, v in env.items() if k != "actual_fish_records"}, indent=2))
    
    print("\nTesting prediction for today...")
    pred = prediction_service.generate_prediction(date.today())
    print(f"Predictions generated successfully. Poseidon top fish: {pred['buoys']['BUOY-POSEIDON']['predictions'][0]['common_name']}")
