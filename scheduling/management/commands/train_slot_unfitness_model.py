"""
Train the Keras slot-unfitness model from SlotPedagogicalFeatures rows.

Requires TensorFlow. After training, greedy + GA scheduling use the saved weights
(MEDIA_ROOT/scheduling_ml/slot_unfitness.keras) via scheduling.ml_predict.

Example::

    python manage.py train_slot_unfitness_model --organization-id 1
"""

from __future__ import annotations

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from scheduling.ml_predict import (
    FEATURE_SIZE,
    clear_model_cache,
    feature_vector_from_row,
    heuristic_from_vector,
    model_file_path,
)
from scheduling.models import SlotPedagogicalFeatures
from university.scope import get_default_organization


class Command(BaseCommand):
    help = "Train Keras slot-unfitness model from pedagogical feature rows"

    def add_arguments(self, parser):
        parser.add_argument(
            "--organization-id",
            type=int,
            default=None,
            help="Organization primary key (default: default org from scope helper)",
        )
        parser.add_argument("--epochs", type=int, default=120)
        parser.add_argument("--batch-size", type=int, default=32)

    def handle(self, *args, **options):
        try:
            import tensorflow as tf
        except Exception as exc:
            raise CommandError(
                "TensorFlow is required for training. Install dependencies from requirements.txt."
            ) from exc

        org_id = options["organization_id"]
        if org_id is None:
            org_id = get_default_organization().id

        rows = list(
            SlotPedagogicalFeatures.objects.filter(organization_id=org_id).select_related("timeslot")
        )
        if len(rows) < 4:
            raise CommandError(
                f"Need at least 4 SlotPedagogicalFeatures rows for org {org_id}; "
                f"found {len(rows)}. Run seed_demo or add data in admin."
            )

        xs: list[list[float]] = []
        ys: list[float] = []
        for row in rows:
            ts = row.timeslot
            vec = feature_vector_from_row(row, ts)
            if row.target_unfitness_label is not None:
                y = float(row.target_unfitness_label)
            else:
                y = heuristic_from_vector(vec)
            xs.append(vec)
            ys.append(max(0.0, min(1.0, y)))

        x = tf.constant(xs, dtype=tf.float32)
        y = tf.constant([[t] for t in ys], dtype=tf.float32)

        model = tf.keras.Sequential(
            [
                tf.keras.layers.Input(shape=(FEATURE_SIZE,)),
                tf.keras.layers.Dense(24, activation="relu"),
                tf.keras.layers.Dense(12, activation="relu"),
                tf.keras.layers.Dense(1, activation="sigmoid"),
            ]
        )
        model.compile(optimizer=tf.keras.optimizers.Adam(0.001), loss="mse", metrics=["mae"])

        epochs = int(options["epochs"])
        batch = int(options["batch_size"])
        val_split = 0.2 if len(rows) >= 10 else 0.0
        fit_kw: dict = {"epochs": epochs, "batch_size": min(batch, len(rows)), "verbose": 1}
        if val_split > 0:
            fit_kw["validation_split"] = val_split

        model.fit(x, y, **fit_kw)

        out: Path = model_file_path()
        out.parent.mkdir(parents=True, exist_ok=True)
        model.save(out)
        clear_model_cache()
        self.stdout.write(self.style.SUCCESS(f"Saved model to {out}"))
