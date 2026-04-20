import pandas as pd
from analysis.amplitude import analyze_lver

# Mock data
df = pd.DataFrame({
    'Shear Strain': [0.1, 1, 10, 100],
    'Storage Modulus': [10000, 9900, 8000, 1000],
    'Loss Modulus': [500, 600, 1200, 800]
})

res = analyze_lver([('test', df)], plateau_points=2, deviation=0.1)
print(res)
