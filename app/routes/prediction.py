from flask import Blueprint, render_template, request, flash, jsonify
from flask_login import login_required, current_user
from app.forms import DirectPredictionForm
from app.services.ml_service import execute_direct_prediction, DATASET_PRESETS, MODEL_FEATURES
import database as db

prediction_bp = Blueprint("prediction", __name__)

@prediction_bp.route("/prediction", methods=["GET", "POST"])
@login_required
def prediction():
    form = DirectPredictionForm()
    prediction_result = None

    if form.validate_on_submit():
        # Build metrics dictionary strictly in MODEL_FEATURES order
        metrics = {}
        for feat in MODEL_FEATURES:
            field = getattr(form, feat, None)
            val = float(field.data) if field and field.data is not None else 0.0
            metrics[feat] = val

        lang = form.language.data
        threshold = float(form.threshold.data)
        dataset_origin = form.dataset_preset.data

        # Run ML defect prediction
        pred_res = execute_direct_prediction(metrics, language=lang, threshold=threshold)

        # Save to MongoDB predictions collection
        pred_id, msg = db.save_prediction_direct(
            user_id=current_user.id,
            dataset_name=dataset_origin,
            software_metrics=metrics,
            defect_probability=pred_res["final_probability"],
            prediction_result=pred_res["prediction_result"],
            threshold_used=threshold,
            ml_probability=pred_res["ml_probability"],
            validation_status=pred_res["validation_status"]
        )

        pred_res["prediction_id"] = pred_id
        prediction_result = pred_res
        flash("Machine learning defect prediction executed successfully!", "success")

    return render_template(
        "prediction.html",
        form=form,
        prediction_result=prediction_result,
        model_features=MODEL_FEATURES
    )


@prediction_bp.route("/prediction/api/preset/<preset_id>")
@login_required
def get_preset_api(preset_id):
    """API endpoint to retrieve dataset preset feature values for client-side auto-fill."""
    preset = DATASET_PRESETS.get(preset_id)
    if preset:
        return jsonify({"success": True, "preset": preset})
    return jsonify({"success": False, "message": "Preset not found"}), 404
