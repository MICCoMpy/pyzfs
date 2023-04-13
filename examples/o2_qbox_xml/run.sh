#!/bin/bash

# The wavefunction used was generated with Qbox 1.67.4 using the following command
# qb < qb.in > qb.out

# Run PyZFS to compute the ZFS tensor
pyzfs --wfcfmt qbox > zfs.out
# An equivalent command is:
# python -m pyzfs.run --wfcfmt qbox > zfs.out

D=`grep --color=never "D unit" zfs.xml | grep --color=never -Eoh '[+-]?[0-9]+([.][0-9]+)?'`
Dref=`grep --color=never "D unit" zfs_ref.xml | grep --color=never -Eoh '[+-]?[0-9]+([.][0-9]+)?'`

E=`grep --color=never "E unit" zfs.xml | grep --color=never -Eoh '[+-]?[0-9]+([.][0-9]+)?'`
Eref=`grep --color=never "E unit" zfs_ref.xml | grep --color=never -Eoh '[+-]?[0-9]+([.][0-9]+)?'`

echo "D = " $D
echo "Ref D = " $Dref
echo "E = " $E
echo "Ref E = " $Eref

if [ `python -c "print(int(abs($D - $Dref) < 1 and abs($E - $Eref) < 1))"` -ne 0 ]
then
    exit 0
else
    exit 1
fi

