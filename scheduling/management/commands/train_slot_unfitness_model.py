"""
Train the Keras slot-unfitness model from SlotPedagogicalFeatures rows.

Default: small Transformer over the weekly slot sequence. Optional --architecture mlp for per-row dense net.
Saves metrics to MEDIA_ROOT/scheduling_ml/training_metrics.json.

Example::

    python manage.py train_slot_unfitness_model --organization-id 1
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from django.core.management.base import BaseCommand, CommandError

from scheduling.ml.keras_arch import build_mlp_model, build_transformer_week_model
from scheduling.ml.predict import (
    FEATURE_SIZE,
    clear_model_cache,
    feature_vector_from_row,
    heuristic_from_vector,
    model_file_path,
)
from scheduling.ml.train_metrics import model_meta_path, write_metrics
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
        parser.add_argument(
            "--architecture",
            choices=("transformer", "mlp"),
            default="transformer",
            help="transformer: sequence over the week; mlp: per-row dense network",
        )

    def handle(self, *args, **options):
        try:
            import tensorflow as tf
        except Exception as exc:
            raise CommandError(
                "TensorFlow is required for training. Install dependencies from requirements.txt."
            ) from exc

        try:
            from sklearn.metrics import accuracy_score, f1_score, mean_absolute_error
        except Exception as exc:
            raise CommandError("scikit-learn is required for training metrics.") from exc

        org_id = options["organization_id"]
        if org_id is None:
            org_id = get_default_organization().id

        rows = list(
            SlotPedagogicalFeatures.objects.filter(organization_id=org_id)
            .select_related("timeslot")
            .order_by("timeslot__day_of_week", "timeslot__period")
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

        slot_ids = [row.timeslot_id for row in rows]
        seq_len = len(xs)
        arch = options["architecture"]
        rng = np.random.default_rng(42)

        if arch == "mlp":
            X = np.asarray(xs, dtype=np.float32)
            Y = np.asarray(ys, dtype=np.float32).reshape(-1, 1)
            xr: list[np.ndarray] = [X]
            yr: list[np.ndarray] = [Y]
            for _ in range(200):
                xr.append(np.clip(X + rng.normal(0.0, 0.035, X.shape).astype(np.float32), 0.0, 1.0))
                yr.append(np.clip(Y + rng.normal(0.0, 0.025, Y.shape).astype(np.float32), 0.0, 1.0))
            xm = np.concatenate(xr, axis=0)
            ym = np.concatenate(yr, axis=0)

            model = build_mlp_model(FEATURE_SIZE)
            model.compile(optimizer=tf.keras.optimizers.Adam(0.001), loss="mse", metrics=["mae"])
            val_split = 0.2 if xm.shape[0] >= 10 else 0.0
            fit_kw: dict = {
                "epochs": int(options["epochs"]),
                "batch_size": min(int(options["batch_size"]), xm.shape[0]),
                "verbose": 1,
            }
            if val_split > 0:
                fit_kw["validation_split"] = val_split
            model.fit(xm, ym, **fit_kw)
            y_pred = model.predict(xm, verbose=0).reshape(-1)
            y_true = ym.reshape(-1)
            h_pred = np.array([heuristic_from_vector(list(xm[i])) for i in range(xm.shape[0])])
            meta = {
                "architecture": "mlp_tabular",
                "seq_len": None,
                "slot_ids": None,
                "organization_id": org_id,
                "feature_size": FEATURE_SIZE,
            }
        else:
            x_week = np.asarray([xs], dtype=np.float32)
            y_week = np.asarray([[ys]], dtype=np.float32)
            n_aug = max(96, seq_len * 8)
            xa = [x_week]
            ya = [y_week]
            for _ in range(n_aug):
                noise_x = rng.normal(0.0, 0.035, x_week.shape).astype(np.float32)
                noise_y = rng.normal(0.0, 0.025, y_week.shape).astype(np.float32)
                xa.append(np.clip(x_week + noise_x, 0.0, 1.0))
                ya.append(np.clip(y_week + noise_y, 0.0, 1.0))
            x_train = np.concatenate(xa, axis=0)
            y_train = np.concatenate(ya, axis=0)

            model = build_transformer_week_model(seq_len, FEATURE_SIZE)
            model.compile(optimizer=tf.keras.optimizers.Adam(0.0008), loss="mse", metrics=["mae"])
            val_split = 0.2 if x_train.shape[0] >= 10 else 0.0
            fit_kw = {
                "epochs": int(options["epochs"]),
                "batch_size": min(int(options["batch_size"]), x_train.shape[0]),
                "verbose": 1,
            }
            if val_split > 0:
                fit_kw["validation_split"] = val_split
            model.fit(x_train, y_train, **fit_kw)
            y_pred = model.predict(x_train, verbose=0).reshape(-1)
            y_true = y_train.reshape(-1)
            flat_dim = x_train.shape[0] * seq_len
            h_pred = np.zeros(flat_dim, dtype=np.float64)
            x_flat = x_train.reshape(-1, FEATURE_SIZE)
            for i in range(flat_dim):
                h_pred[i] = heuristic_from_vector(list(x_flat[i]))
            meta = {
                "architecture": "transformer_week",
                "seq_len": seq_len,
                "slot_ids": slot_ids,
                "organization_id": org_id,
                "feature_size": FEATURE_SIZE,
            }

        y_bin = (y_true >= 0.5).astype(int)
        y_pred_bin = (y_pred >= 0.5).astype(int)
        acc = float(accuracy_score(y_bin, y_pred_bin))
        f1 = float(f1_score(y_bin, y_pred_bin, zero_division=0))
        mae_model = float(mean_absolute_error(y_true, y_pred))
        mae_heur = float(mean_absolute_error(y_true, h_pred))

        out: Path = model_file_path()
        out.parent.mkdir(parents=True, exist_ok=True)
        model.save(out)

        meta_path = model_meta_path()
        meta_path.parent.mkdir(parents=True, exist_ok=True)
        meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")

        metrics_payload = {
            "architecture": meta["architecture"],
            "organization_id": org_id,
            "epochs": int(options["epochs"]),
            "mae_model": round(mae_model, 6),
            "mae_heuristic_baseline": round(mae_heur, 6),
            "binary_accuracy": round(acc, 6),
            "f1_score": round(f1, 6),
            "before_after": {
                "metric": "mean_absolute_error_vs_labels",
                "heuristic": round(mae_heur, 6),
                "trained_model": round(mae_model, 6),
            },
        }
        mp = write_metrics(metrics_payload)

        clear_model_cache()
        self.stdout.write(self.style.SUCCESS(f"Saved model to {out}"))
        self.stdout.write(self.style.SUCCESS(f"Saved metrics to {mp}"))
        self.stdout.write(
            self.style.SUCCESS(
                f"MAE model={metrics_payload['mae_model']}, MAE heuristic={metrics_payload['mae_heuristic_baseline']}, "
                f"acc={metrics_payload['binary_accuracy']}, F1={metrics_payload['f1_score']}"
            )
        )
