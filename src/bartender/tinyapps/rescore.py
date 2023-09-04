"""Rescore a HADDOCK run with different weights."""
from pathlib import Path
from string import Template

from pydantic import BaseModel

from bartender.tinyapps import TinyAppResult, shell


class TinyArguments(BaseModel):
    module: int
    w_elec: float
    w_vdw: float
    w_desolv: float
    w_bsa: float
    w_air: float


async def main(tinyargs: TinyArguments, job_dir: Path) -> TinyAppResult:
    # TODO get template from config,
    # so location of haddock3-int_rescore executable
    # is configurable without changing code?
    command_template = Template(
        """haddock3-int_rescore \
        --run-dir output \
        --module $module \
        --w_elec $w_elec --w_vdw $w_vdw --w_desolv $w_desolv --w_bsa $w_bsa --w_air $w_air""",
    )
    command = command_template.substitute(tinyargs.dict())
    # TODO return path where results of command are stored
    # depends on arguments.module
    return await shell(job_dir, command)
