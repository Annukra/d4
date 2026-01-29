import os
import subprocess
import csv
import matplotlib.pyplot as plt

class Uad():
    def __init__(self):
        self.inst = None

    def reset(self):
        return os.system(f'{self.inst} com --action reset')

    def enable(self):
        return os.system(f'{self.inst} com --action enable')

    def read_CSR(self):
        csr_bytes = subprocess.check_output(f'{self.inst} cfg --address 0x0', shell=True)
        return int(csr_bytes, 0)
    
    def write_CSR(self, data):
        return os.system(f'{self.inst} cfg --address 0x0 --data {hex(data)}')
    
    def read_COEF(self):
        """Read COEF register at address 0x4"""
        coef_bytes = subprocess.check_output(f'{self.inst} cfg --address 0x4', shell=True)
        return int(coef_bytes, 0)
    
    def write_COEF(self, data):
        """Write to COEF register at address 0x4"""
        return os.system(f'{self.inst} cfg --address 0x4 --data {hex(data)}')
    
    def set_halt(self):
        csr = self.read_CSR()
        csr |= (1 << 5)  # Set HALT bit
        self.write_CSR(csr)

    def clear_halt(self):
        csr = self.read_CSR()
        csr &= ~(1 << 5)  # Clear HALT bit
        self.write_CSR(csr)
    
    def clear_taps(self):
        """Clear filter taps"""
        csr = self.read_CSR()
        csr |= (1 << 18)  # Set TCLR bit
        self.write_CSR(csr)
    
    def enable_filter(self):
        """Enable filter (FEN = 1)"""
        csr = self.read_CSR()
        csr |= (1 << 0)  # Set FEN bit
        self.write_CSR(csr)
    
    def send_signal(self, data):
        output_bytes = subprocess.check_output(f'{self.inst} sig --data {hex(data)}', shell=True)
        output_str = output_bytes.strip()
        if output_str:
            return int(output_str, 0)
        else:
            return None


def load_config(filename):
    """Read configuration file and return coefficients"""
    coeffs = {}
    with open(filename, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            coef_num = int(row['coef'])
            coeffs[coef_num] = {
                'enabled': int(row['en']),
                'value': int(row['value'], 16)
            }
    return coeffs


def load_vector(filename):
    """Read vector file and return list of input signals"""
    with open(filename, 'r') as f:
        content = f.read()
        # Split by whitespace and convert to integers
        values = [int(x, 16) for x in content.split()]
    return values


def configure_filter(uad, config):
    """Configure the filter with given coefficients"""
    print("\n--- Configuring Filter ---")
    
    # Step 1: HALT the filter
    uad.set_halt()
    print("✓ Filter halted")
    
    # Step 2: Build COEF register value
    # COEF format: [C3][C2][C1][C0] - each coefficient is 8 bits
    coef_value = 0
    coef_value |= (config[0]['value'] << 0)   # C0 in bits 0-7
    coef_value |= (config[1]['value'] << 8)   # C1 in bits 8-15
    coef_value |= (config[2]['value'] << 16)  # C2 in bits 16-23
    coef_value |= (config[3]['value'] << 24)  # C3 in bits 24-31
    
    uad.write_COEF(coef_value)
    print(f"✓ Coefficients written: {hex(coef_value)}")
    
    # Step 3: Set coefficient enable bits in CSR
    csr = uad.read_CSR()
    
    # Clear all coefficient enable bits first
    csr &= ~(1 << 1)  # Clear C0EN
    csr &= ~(1 << 2)  # Clear C1EN
    csr &= ~(1 << 3)  # Clear C2EN
    csr &= ~(1 << 4)  # Clear C3EN
    
    # Set enabled coefficients
    if config[0]['enabled']:
        csr |= (1 << 1)  # C0EN
    if config[1]['enabled']:
        csr |= (1 << 2)  # C1EN
    if config[2]['enabled']:
        csr |= (1 << 3)  # C2EN
    if config[3]['enabled']:
        csr |= (1 << 4)  # C3EN
    
    uad.write_CSR(csr)
    print(f"✓ Coefficient enables set")
    
    # Step 4: Clear filter taps
    uad.clear_taps()
    print("✓ Filter taps cleared")
    
    # Step 5: Un-halt the filter
    uad.clear_halt()
    print("✓ Filter un-halted")
    
    # Step 6: Enable filter
    uad.enable_filter()
    print("✓ Filter enabled")


def process_signals(uad, input_signals):
    """Send signals through filter and collect outputs"""
    print(f"\n--- Processing {len(input_signals)} signals ---")
    
    outputs = []
    for i, input_val in enumerate(input_signals):
        output_val = uad.send_signal(input_val)
        outputs.append(output_val)
        print(f"Signal {i+1:2d}: Input={hex(input_val)} → Output={hex(output_val) if output_val else 'None'}")
    
    return outputs


def plot_results(all_results, input_signals):
    """Create graphs for all configuration results"""
    
    # Create a figure with subplots for each configuration
    num_configs = len(all_results)
    fig, axes = plt.subplots(num_configs, 1, figsize=(12, 4*num_configs))
    
    # If only one config, axes won't be an array
    if num_configs == 1:
        axes = [axes]
    
    sample_indices = range(len(input_signals))
    
    for idx, (cfg_name, outputs) in enumerate(all_results.items()):
        ax = axes[idx]
        
        # Plot input and output signals
        ax.plot(sample_indices, input_signals, 'b-o', label='Input', markersize=4, linewidth=1.5)
        ax.plot(sample_indices, outputs, 'r-s', label='Output', markersize=4, linewidth=1.5)
        
        ax.set_xlabel('Sample Index')
        ax.set_ylabel('Signal Value')
        ax.set_title(f'Filter Response - {cfg_name}')
        ax.legend()
        ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig('filter_results.png', dpi=150, bbox_inches='tight')
    print(f"\n✓ Graph saved as 'filter_results.png'")
    plt.show()


def plot_comparison(all_results, input_signals):
    """Create a comparison plot showing all configurations"""
    
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10))
    
    sample_indices = range(len(input_signals))
    
    # Plot 1: Input vs all outputs
    ax1.plot(sample_indices, input_signals, 'k-', label='Input', linewidth=2, alpha=0.7)
    
    colors = ['red', 'blue', 'green', 'orange']
    for idx, (cfg_name, outputs) in enumerate(all_results.items()):
        color = colors[idx % len(colors)]
        ax1.plot(sample_indices, outputs, marker='o', label=cfg_name, 
                color=color, markersize=3, linewidth=1.5, alpha=0.8)
    
    ax1.set_xlabel('Sample Index')
    ax1.set_ylabel('Signal Value')
    ax1.set_title('Filter Comparison - All Configurations')
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    
    # Plot 2: Difference from input (filter effect)
    for idx, (cfg_name, outputs) in enumerate(all_results.items()):
        color = colors[idx % len(colors)]
        differences = [out - inp for inp, out in zip(input_signals, outputs)]
        ax2.plot(sample_indices, differences, marker='o', label=cfg_name, 
                color=color, markersize=3, linewidth=1.5, alpha=0.8)
    
    ax2.axhline(y=0, color='k', linestyle='--', linewidth=1, alpha=0.5)
    ax2.set_xlabel('Sample Index')
    ax2.set_ylabel('Output - Input (Filter Effect)')
    ax2.set_title('Filter Effect on Signal')
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig('filter_comparison.png', dpi=150, bbox_inches='tight')
    print(f"✓ Comparison graph saved as 'filter_comparison.png'")
    plt.show()


# ==================== MAIN PROGRAM ====================

# Setup
uad = Uad()
uad.inst = "impl0"

# Configuration files to test
config_files = ["p0.cfg", "p4.cfg", "p7.cfg", "p9.cfg"]

# Load input vector
input_signals = load_vector("sqr.vec")
print(f"Loaded {len(input_signals)} input signals from sqr.vec")

# Dictionary to store all results
all_results = {}

# Test each configuration
for cfg_file in config_files:
    print("\n" + "=" * 60)
    print(f"TESTING CONFIGURATION: {cfg_file}")
    print("=" * 60)
    
    # Reset and enable IP
    uad.reset()
    uad.enable()
    
    # Load configuration
    config = load_config(cfg_file)
    print(f"\nConfiguration:")
    for i in range(4):
        status = "ENABLED" if config[i]['enabled'] else "DISABLED"
        print(f"  C{i}: {hex(config[i]['value'])} ({status})")
    
    # Configure filter
    configure_filter(uad, config)
    
    # Process signals
    outputs = process_signals(uad, input_signals)
    
    # Store results
    all_results[cfg_file] = outputs

print("\n" + "=" * 60)
print("ALL CONFIGURATIONS TESTED!")
print("=" * 60)

# Generate graphs
print("\n--- Generating Graphs ---")
plot_results(all_results, input_signals)
plot_comparison(all_results, input_signals)

print("\n✓ All graphs generated successfully!")
