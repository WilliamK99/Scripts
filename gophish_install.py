

#!/usr/bin/env python3
import subprocess
import os
import json
import re
import time

# This script will help automate the install of gophish, automatically updating the config.json file on a Digital Ocean applet.  
# Certs will be updated from certbot but you must manually add DNS settings on namecheap

def run_command(command, check=True):
    """Run a shell command and handle errors."""
    try:
        result = subprocess.run(command, shell=True, check=check, text=True, capture_output=True)
        return result.stdout, result.stderr
    except subprocess.CalledProcessError as e:
        print(f"Error running command '{command}': {e.stderr}")
        return None, e.stderr

def edit_config_json(gophish_dir, updates):
    """Edit config.json with provided key-value pairs."""
    config_path = os.path.join(gophish_dir, "config.json")
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        # Update the config dictionary
        for key, value in updates.items():
            if key in config:
                config[key] = value
            else:
                # For nested updates like cert_path and key_path
                section, subkey = key.split('.')
                if section in config:
                    config[section][subkey] = value
                else:
                    print(f"Section {section} not found in config.json")
                    return False
        
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=4)
        print(f"Updated {config_path} with {updates}")
        return True
    except Exception as e:
        print(f"Error editing {config_path}: {e}")
        return False

def main():
    # Step 1: Update system and install dependencies
    print("Running apt update...")
    run_command("apt update")
    
    print("Running apt upgrade...")
    run_command("apt upgrade -y")
    
    print("Installing unzip and certbot...")
    run_command("apt install unzip certbot -y")
    
    # Step 2: Create gophish directory if it doesn't exist
    gophish_dir = "gophish"
    if not os.path.exists(gophish_dir):
        print(f"Creating directory {gophish_dir}...")
        os.makedirs(gophish_dir)
    
    # Step 3: Navigate to gophish directory
    os.chdir(gophish_dir)
    print(f"Changed to directory: {os.getcwd()}")
    
    # Step 4: Download Gophish
    gophish_url = "https://github.com/gophish/gophish/releases/download/v0.12.1/gophish-v0.12.1-linux-64bit.zip"
    print(f"Downloading Gophish from {gophish_url}...")
    run_command(f"wget {gophish_url}")
    
    # Step 5: Unzip Gophish
    zip_file = "gophish-v0.12.1-linux-64bit.zip"
    print(f"Unzipping {zip_file}...")
    run_command(f"unzip -o {zip_file}")
    
    # Step 6: Make gophish binary executable
    print("Making gophish binary executable...")
    run_command("chmod +x gophish")
    
    # Step 7: Edit config.json to set listen_url
    print("Updating config.json with listen_url...")
    if not edit_config_json(os.getcwd(), {"listen_url": "0.0.0.0:3333"}):
        print("Failed to update config.json. Exiting.")
        return
    
    # Step 8: Prompt for domain and run Certbot
    domain = input("Enter your domain for Certbot (e.g., example.com): ").strip()
    certbot_cmd = (
        f"certbot certonly -d {domain} --manual --preferred-challenges dns "
        "--register-unsafely-without-email --agree-tos"
    )
    print(f"Running Certbot: {certbot_cmd}")
    
    # Run Certbot and capture output
    stdout, stderr = run_command(certbot_cmd, check=False)
    
    if stdout or stderr:
        combined_output = (stdout or "") + (stderr or "")
        
        # Step 9: Extract _acme-challenge string and value
        acme_pattern = r"Please deploy a DNS TXT record under the name:\s*(_acme-challenge\.[^\s]+)\s*with the following value:\s*([^\s]+)"
        acme_match = re.search(acme_pattern, combined_output)
        
        if acme_match:
            acme_name, acme_value = acme_match.groups()
            print(f"\nPlease update your DNS records with the following:")
            print(f"Name: {acme_name}")
            print(f"Value: {acme_value}")
            print("Wait approximately 1 minute after updating DNS, then press Enter to continue...")
            input()  # Wait for user confirmation
        else:
            print("Failed to extract _acme-challenge details. Check Certbot output.")
            print(combined_output)
            return
        
        # Step 10: Check Certbot success and extract cert_path and key_path
        success_pattern = r"Successfully received certificate\..*?Certificate is saved at:\s*([^\s]+).*?Key is saved at:\s*([^\s]+)"
        success_match = re.search(success_pattern, combined_output, re.DOTALL)
        
        if success_match:
            cert_path, key_path = success_match.groups()
            print("Certbot succeeded!")
            print(f"Certificate path: {cert_path}")
            print(f"Key path: {key_path}")
            
            # Step 11: Update config.json with cert_path and key_path
            updates = {
                "phish_server.use_tls": True,
                "phish_server.cert_path": cert_path,
                "phish_server.key_path": key_path
            }
            if not edit_config_json(os.getcwd(), updates):
                print("Failed to update config.json with certificate paths. Exiting.")
                return
            print("Gophish installation and configuration completed successfully!")
        else:
            print("Certbot failed. Check the output for errors:")
            print(combined_output)
            return
    else:
        print("No output from Certbot. Possible failure or interruption.")
        return

if __name__ == "__main__":
    # Ensure script is run with sudo
    if os.geteuid() != 0:
        print("This script must be run as root (use sudo).")
        exit(1)
    
    try:
        main()
    except KeyboardInterrupt:
        print("\nScript interrupted by user.")
        exit(1)
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        exit(1)
