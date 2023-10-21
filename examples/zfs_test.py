import pytest
import numpy as np
from xml.etree import ElementTree as ET


def read_zfs(fileName):
    xmlData = ET.parse(fileName)
    D = float(xmlData.find("D").text)
    E = float(xmlData.find("E").text)

    return D, E


@pytest.mark.parametrize("testdir", ["o2_qbox_xml", "o2_qe_hdf5"])
def test_zfs(testdir):
    file_new = f"{testdir}/zfs.xml"
    file_ref = f"{testdir}/zfs_ref.xml"

    D_new, E_new = read_zfs(file_new)
    D_ref, E_ref = read_zfs(file_ref)

    D_diff = np.abs(D_new - D_ref)
    E_diff = np.abs(E_new - E_ref)

    print(f"D diff: {D_diff} MHz")
    print(f"E diff: {E_diff} MHz")

    assert D_diff < 1e-3
    assert E_diff < 1e-3
