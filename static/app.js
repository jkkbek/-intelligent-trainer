const steps = document.querySelectorAll(".form-step");
const indicators = document.querySelectorAll(".step");
const prevBtn = document.getElementById("prevBtn");
const nextBtn = document.getElementById("nextBtn");
const submitBtn = document.getElementById("submitBtn");
const progressFill = document.getElementById("progressFill");

let currentStep = 0;

function getCurrentStepRequiredFields() {
    if (!steps.length) return [];
    return Array.from(steps[currentStep].querySelectorAll("[required]"));
}

function validateCurrentStep() {
    const requiredFields = getCurrentStepRequiredFields();
    let isValid = true;

    requiredFields.forEach((field) => {
        if (!field.value || field.value.trim() === "") {
            field.classList.add("field-error");
            isValid = false;
        } else {
            field.classList.remove("field-error");
        }
    });

    return isValid;
}

function updateProgress() {
    if (!progressFill || !steps.length) return;
    const progress = ((currentStep + 1) / steps.length) * 100;
    progressFill.style.width = `${progress}%`;
}

function updateSteps() {
    if (!steps.length) return;

    steps.forEach((step, index) => {
        step.classList.toggle("active", index === currentStep);
    });

    indicators.forEach((indicator, index) => {
        indicator.classList.toggle("active", index === currentStep);
    });

    if (prevBtn) {
        prevBtn.style.display = currentStep === 0 ? "none" : "inline-block";
    }

    if (nextBtn) {
        nextBtn.classList.toggle("hidden", currentStep === steps.length - 1);
    }

    if (submitBtn) {
        submitBtn.classList.toggle("hidden", currentStep !== steps.length - 1);
    }

    updateProgress();
}

if (nextBtn) {
    nextBtn.addEventListener("click", () => {
        if (!validateCurrentStep()) return;

        if (currentStep < steps.length - 1) {
            currentStep++;
            updateSteps();
        }
    });
}

if (prevBtn) {
    prevBtn.addEventListener("click", () => {
        if (currentStep > 0) {
            currentStep--;
            updateSteps();
        }
    });
}

document.querySelectorAll("input, select").forEach((field) => {
    field.addEventListener("input", () => {
        if (field.hasAttribute("required")) {
            if (field.value && field.value.trim() !== "") {
                field.classList.remove("field-error");
            }
        }
    });
});

updateSteps();