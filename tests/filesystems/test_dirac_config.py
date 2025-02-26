import pytest

from bartender.filesystems.dirac_config import DiracFileSystemConfig


class TestDiracFileSystemConfig:
    def test_lfn_root_nodots(self) -> None:
        config = DiracFileSystemConfig(
            lfn_root="/tutoVO/user/c/ciuser/bartenderjobs",
            storage_element="StorageElementOne",
        )
        assert isinstance(config, DiracFileSystemConfig)

    def test_lfn_root_withdots(self) -> None:
        config = DiracFileSystemConfig(
            lfn_root="/tuto.VO/user/c/ciuser/bartender.jobs",
            storage_element="StorageElementOne",
        )
        assert isinstance(config, DiracFileSystemConfig)

    def test_lfn_root_initial_not_first(self) -> None:
        config = DiracFileSystemConfig(
            lfn_root="/tuto.VO/user/o/someone/bartenderjobs",
            storage_element="StorageElementOne",
        )
        assert isinstance(config, DiracFileSystemConfig)

    def test_lfn_root_bad(self) -> None:
        with pytest.raises(ValueError):
            DiracFileSystemConfig(
                lfn_root="/",
                storage_element="StorageElementOne",
            )
