Each folder in this directory contains a test example for the PyZFS code.

* `o2_qbox_xml`: calculation of the ZFS tensor for the O2 molecule using Qbox wavefunctions in XML format.
* `o2_qe_hdf5`: calculation of the ZFS tensor for the O2 molecule using Quantum Espresso wavefunctions in HDF5 format.
* `diamond_nv_qe_hdf5`: calculation of the ZFS tensor for the negatively-charged nitrogen-vacancy center in diamond using Quantum Espresso wavefunctions in HDF5 format.

Each folder contains a `run.sh` file, which can be executed to compute the ZFS tensor and compare with reference values. These scripts are also used for automatic testing of the code. In particular, the scalar `D` and `E` parameters will be extracted from the ZFS tensor and compared with reference values `Ref D` and `Ref E`. The computed and reference values should be identical.

Note that for the `diamond_nv_qe_hdf5` example, the wavefunctions are not stored in the repository because of their size. One needs to install Quantum Espresso with HDF5 enabled and run a DFT calculation to obtain the wavefunctions.
