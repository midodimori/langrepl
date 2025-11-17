from pathlib import Path

from src.cli.bootstrap.timer import enable_timer
from src.cli.core.context import Context
from src.cli.core.session import Session
from src.cli.theme import console


async def handle_chat_command(args) -> int:
    """Handle the chat command."""
    try:
        if args.timer:
            enable_timer()

        context = await Context.create(
            agent=args.agent,
            model=args.model,
            resume=args.resume,
            working_dir=Path(args.working_dir),
            approval_mode=args.approval_mode,
        )

        session = Session(context)

        # One-shot mode
        if args.message:
            if args.resume:
                await session.command_dispatcher.resume_handler.handle(
                    context.thread_id, render_history=False
                )
            return await session.send(args.message)

        # Interactive mode
        first_start = True
        while True:
            if first_start and args.resume:
                await session.command_dispatcher.resume_handler.handle(
                    context.thread_id
                )

            await session.start(show_welcome=first_start and not args.resume)
            first_start = False

            if session.needs_reload:
                session = Session(context)
                continue
            else:
                break

        return 0
    except KeyboardInterrupt:
        return 0
    except Exception as e:
        console.print_error(f"Error starting chat session: {e}")
        console.print("")
        return 1
