## **PyZFS** code repository

**PyZFS** is a Python package for first-principles calculations of the zero-field-splitting (ZFS) tensor of molecules and materials based on wavefunctions obtained from density functional theory (DFT) calculations.

The ZFS tensor describes the lifting of degeneracy of spin sublevels in the absence of external magnetic fields, and is an important property of open-shell molecules and spin defects in semiconductors with spin quantum number S > 1. Some prototypical spin defects with nonzero ZFS tensors include the nitrogen-vacancy center in diamond and divacancies in silicon carbide. **PyZFS** can compute the spin-spin component of the ZFS tensor for molecules and materials, using wavefunctions from plane-wave DFT codes such as [Quantum Espresso](https://www.quantum-espresso.org/) and [Qbox](http://qboxcode.org/).

**PyZFS** supports parallelization via [mpi4py](https://mpi4py.readthedocs.io/en/stable/) and NVIDIA GPU acceleration via [CuPy](https://cupy.dev/).

Documentation
-------------

The tutorial and documentation are hosted on [Read the Docs](https://pyzfs-doc.readthedocs.io/en/latest/).

Authors
-------

He Ma (mahe@uchicago.edu)

Marco Govoni (mgovoni@anl.gov)

Giulia Galli (gagalli@uchicago.edu)

Victor Yu (yuw@anl.gov)

Contact
-------

Please use the GitHub [issue tracker](https://github.com/MICCoMPy/pyzfs/issues) for bug reports. Contributions to new features are welcome.
