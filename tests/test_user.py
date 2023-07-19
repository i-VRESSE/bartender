from pathlib import Path

from pytest import CaptureFixture

from bartender.user import JwtDecoder, generate_token_subcommand


def test_generate_token_subcommand(
    rsa_private_key: bytes,
    demo_jwt_decoder: JwtDecoder,
    tmp_path: Path,
    capsys: CaptureFixture[str],
) -> None:
    private_key_file = tmp_path / "private_key.pem"
    private_key_file.write_bytes(rsa_private_key)

    generate_token_subcommand(
        private_key=private_key_file,
        username="test",
        roles=["test"],
        lifetime=100,
        issuer="test",
        oformat="plain",
    )

    captured = capsys.readouterr()
    token = captured.out.strip()
    user = demo_jwt_decoder(token)
    assert user.username == "test"
    assert user.roles == ["test"]
    assert user.apikey == token
