from deep_coder.tui.commands.base import CommandBase, CommandMatch, CommandResult


DOC_MODEL_OPTIONS = ("deepseek-chat", "deepseek-reasoner")


class ModelCommand(CommandBase):
    name = "model"
    summary = "Select the active model"
    argument_hint = "<model-name>"

    def complete(self, context, args: str):
        prefix = args.strip()
        return [
            self._model_match(model_name)
            for model_name in _available_model_names(context)
            if model_name.startswith(prefix)
        ]

    def execute(self, context, args: str) -> CommandResult:
        model_name = args.strip()
        if not model_name:
            return CommandResult(
                status_message="select a model",
            )

        context.runtime["config"].model_name = model_name
        context.runtime["model"].config.model_name = model_name
        registry = context.runtime.get("registry")
        if registry is not None:
            registry.set_default_model(model_name)
        return CommandResult(updated_model_name=model_name)

    @staticmethod
    def _model_match(model_name: str):
        return CommandMatch(
            name=model_name,
            summary="DeepSeek API model",
            label=model_name,
            command_text=f"/model {model_name}",
            kind="model",
        )


def _available_model_names(context) -> tuple[str, ...]:
    cache_key = "_deepseek_model_names"
    cached = context.runtime.get(cache_key)
    if cached is not None:
        return cached

    model = context.runtime.get("model")
    if model is not None and hasattr(model, "list_models"):
        try:
            names = tuple(model.list_models())
            if names:
                context.runtime[cache_key] = names
                return names
        except Exception:
            pass

    context.runtime[cache_key] = DOC_MODEL_OPTIONS
    return DOC_MODEL_OPTIONS
