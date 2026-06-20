# sg_transit_weather_mesh/utils.py
import yaml
import os

def load_config():
    """Dynamically locates the root config folder and loads config.yaml."""
    # Traces directory execution path up to root, then steps cleanly down into config/
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_path = os.path.join(base_dir, "config", "config.yaml")
    
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Missing configuration mapping layer target: {config_path}")
        
    with open(config_path, "r") as file:
        return yaml.safe_load(file)
