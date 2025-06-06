.. _installation:

Installation
============

**PyZFS** uses the **mpi4py** package for parallelization. An existing MPI implementation (e.g. **MPICH** or **OpenMPI**) is required to install **mpi4py** and **PyZFS**. Many supercomputers provide modules for pre-compiled MPI implementations. MPI can also be installed from package managers such as APT and Homebrew, or built from source.

**PyZFS** requires Python 3.6+. It is recommended to install **PyZFS** using **pip**. First, clone the git repository:

.. code:: bash

   $ git clone https://github.com/MICCoMPy/pyzfs.git

Then, execute **pip** in the folder containing **setup.py**

.. code:: bash

   $ pip install .

**PyZFS** depends on the following packages, which will be installed automatically by **pip**

   - ``numpy``
   - ``scipy``
   - ``mpi4py``
   - ``h5py``
   - ``ase``
   - ``lxml``

If using **pip** is not possible, one can manually install the above dependencies, and then add the directory of **PyZFS** to the ``PYTHONPATH`` environment variable by, e.g.,

.. code:: bash

   # Bash shell as an example
   $ export PYTHONPATH=$PYTHONPATH:path/to/pyzfs

GPU
---

**PyZFS** optionally uses the **cupy** package to offload the calculation to NVIDIA GPUs. To use this feature, install **cupy** by, e.g.,

.. code:: bash

   $ pip install cupy-cuda110

Note that the version of **cupy** must be compatible to the version of CUDA installed on the system, which in the above example is version 11.0. At runtime, **PyZFS** automatically tries to import the **cupy** module and uses all available GPUs. If **cupy** cannot be imported, **PyZFS** falls back to **NumPy** and runs on CPUs.
