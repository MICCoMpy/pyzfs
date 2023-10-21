# Unit conversions
from scipy.constants import h

# Energy
rydberg_to_ev = 13.606
rydberg_to_hartree = 0.5
hartree_to_rydberg = 2.0
hartree_to_ev = 27.212
joule_to_hz = 1.0 / h
hz_to_joule = h
joule_to_mhz = 1.0e-6 / h
mhz_to_joule = 1.0e6 * h
cminv_to_hz = 2.99793e10

# Length
bohr_to_angstrom = 0.52918
angstrom_to_bohr = 1.0 / bohr_to_angstrom
angstrom_to_cm = 1.0e-8
angstrom_to_m = 1.0e-10
bohr_to_m = bohr_to_angstrom * angstrom_to_m
m_to_bohr = 1.0 / bohr_to_m

# Time
fs_to_s = 1.0e-15
