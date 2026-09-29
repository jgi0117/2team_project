"""Qwen 기반 요약 기능의 공통 CLI 옵션."""

from .qwen import QwenSelector


def add_backend_options(parser):
    parser.add_argument("--backend", choices=["qwen", "template"], default="qwen")
    parser.add_argument("--model", default="Qwen/Qwen3-1.7B")
    parser.add_argument("--device", default="cpu", help="cpu 또는 cuda:0")
    parser.add_argument("--local-files-only", action="store_true")


def selector_from_args(args):
    if args.backend == "template":
        return None
    return QwenSelector(args.model, device=args.device, local_files_only=args.local_files_only)
