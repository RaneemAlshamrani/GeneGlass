
const loginForm = document.getElementById("loginForm");
const togglePassword = document.getElementById("togglePassword");
const passwordInput = document.getElementById("password");
const emailInput = document.getElementById("email");
const rememberInput = document.getElementById("remember");
const errorMessage = document.getElementById("errorMessage");
const submitButton = loginForm.querySelector('button[type="submit"]');

const signupForm = document.getElementById("signupForm");
const signupName = document.getElementById("signupName");
const signupEmail = document.getElementById("signupEmail");
const signupPassword = document.getElementById("signupPassword");
const confirmPassword = document.getElementById("confirmPassword");
const signupError = document.getElementById("signupError");
const signupButton = document.getElementById("signupButton");

const loginHeader = document.querySelector(".login-header");
const loginSwitch = document.getElementById("loginSwitch");
const signupSuccess = document.getElementById("signupSuccess");

// Forgot Password elements
const forgotPasswordLink = document.getElementById("forgotPasswordLink");
const forgotPasswordForm = document.getElementById("forgotPasswordForm");
const forgotEmail = document.getElementById("forgotEmail");
const forgotError = document.getElementById("forgotError");
const forgotSuccess = document.getElementById("forgotSuccess");
const forgotButton = document.getElementById("forgotButton");

// Reset Password elements
const resetPasswordForm = document.getElementById("resetPasswordForm");
const resetToken = document.getElementById("resetToken");
const newResetPassword = document.getElementById("newResetPassword");
const confirmResetPassword = document.getElementById("confirmResetPassword");
const resetError = document.getElementById("resetError");
const resetSuccess = document.getElementById("resetSuccess");
const resetButton = document.getElementById("resetButton");

// ===============================
// SHOW / HIDE PASSWORD
// ===============================

togglePassword.addEventListener("click", function () {
    passwordInput.type =
        passwordInput.type === "password" ? "text" : "password";
});

// Show / Hide Password in Sign Up
document.querySelectorAll("[data-password-target]").forEach(button => {
    button.addEventListener("click", function () {
        const inputId = this.dataset.passwordTarget;
        const input = document.getElementById(inputId);

        if (!input) return;

        const isHidden = input.type === "password";

        input.type = isHidden ? "text" : "password";

        this.setAttribute(
            "aria-label",
            isHidden ? "Hide password" : "Show password"
        );
    });
});
// ===============================
// SWITCH BETWEEN LOGIN AND SIGNUP
// ===============================

function hideAllAuthForms() {
    loginForm.hidden = true;
    signupForm.hidden = true;
    forgotPasswordForm.hidden = true;
    resetPasswordForm.hidden = true;
}

function openLoginForm() {
    hideAllAuthForms();

    loginForm.hidden = false;
    loginSwitch.hidden = false;

    loginHeader.querySelector("h1").textContent = "Welcome back";
    loginHeader.querySelector("p").textContent = "Sign in to your account";

    signupError.classList.remove("show");
    forgotError.classList.remove("show");
    resetError.classList.remove("show");
}

function openSignupForm() {
    hideAllAuthForms();

    signupForm.hidden = false;
    loginSwitch.hidden = true;
    signupSuccess.hidden = true;

    loginHeader.querySelector("h1").textContent = "Create Account";
    loginHeader.querySelector("p").textContent =
        "Create your GeneGlass specialist account";

    signupError.classList.remove("show");
}

function openForgotPasswordForm() {
    hideAllAuthForms();

    loginSwitch.hidden = true;
    forgotPasswordForm.hidden = false;
    forgotEmail.value = emailInput.value.trim();

    forgotError.classList.remove("show");
    forgotSuccess.hidden = true;

    loginHeader.querySelector("h1").textContent = "Forgot Password";
    loginHeader.querySelector("p").textContent =
        "We will email you a password reset link";
}

function openResetPasswordForm() {
    hideAllAuthForms();

    loginSwitch.hidden = true;
    resetPasswordForm.hidden = false;

    resetError.classList.remove("show");
    resetSuccess.hidden = true;

    loginHeader.querySelector("h1").textContent = "Reset Password";
    loginHeader.querySelector("p").textContent =
        "Choose your new password";
}

// Reset tokens are delivered in the URL fragment, not shown or typed in the UI.
// Remove the token from the address bar immediately after reading it.
const emailedResetToken = new URLSearchParams(window.location.hash.slice(1)).get("reset");
if (emailedResetToken) {
    window.history.replaceState(null, "", window.location.pathname + window.location.search);
    resetToken.value = emailedResetToken;
    openResetPasswordForm();
}

document.getElementById("showSignup").addEventListener("click", function (event) {
    event.preventDefault();
    openSignupForm();
});

document.getElementById("showLogin").addEventListener("click", function (event) {
    event.preventDefault();
    openLoginForm();
});

forgotPasswordLink.addEventListener("click", function (event) {
    event.preventDefault();
    openForgotPasswordForm();
});

document.getElementById("backToLoginFromForgot").addEventListener("click", function (event) {
    event.preventDefault();
    openLoginForm();
});

document.getElementById("backToLoginFromReset").addEventListener("click", function (event) {
    event.preventDefault();
    openLoginForm();
});

// ===============================
// LOGIN
// ===============================

loginForm.addEventListener("submit", async function (event) {
    event.preventDefault();

    errorMessage.classList.remove("show");
    submitButton.disabled = true;
    submitButton.querySelector("span").textContent = "Signing in...";

    try {
        const body = new URLSearchParams({
            username: emailInput.value.trim(),
            password: passwordInput.value,
        });

        const response = await fetch(
            `${window.GeneGlassConfig.apiBaseUrl}/auth/login`,
            {
                method: "POST",
                headers: {
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                body,
            }
        );

        if (!response.ok) {
            const error = await response.json().catch(() => null);
            throw new Error(error?.detail || "Unable to sign in");
        }

        const auth = await response.json();
        const storage = rememberInput.checked ? localStorage : sessionStorage;

        localStorage.removeItem("geneglass_access_token");
        localStorage.removeItem("geneglass_user");
        sessionStorage.removeItem("geneglass_access_token");
        sessionStorage.removeItem("geneglass_user");

        storage.setItem("geneglass_access_token", auth.access_token);
        storage.setItem("geneglass_user", JSON.stringify(auth.user));

        window.location.replace("../DashboardPage/dashboard.html");

    } catch (error) {
        errorMessage.textContent =
            error.message === "Failed to fetch"
                ? "Cannot reach the GeneGlass server. Make sure the backend is running."
                : error.message;

        errorMessage.classList.add("show");

    } finally {
        submitButton.disabled = false;
        submitButton.querySelector("span").textContent = "Sign In";
    }
});

// ===============================
// FORGOT PASSWORD
// ===============================

forgotPasswordForm.addEventListener("submit", async function (event) {
    event.preventDefault();

    forgotError.classList.remove("show");
    forgotSuccess.hidden = true;

    forgotButton.disabled = true;
    forgotButton.querySelector("span").textContent = "Sending...";

    try {
        const response = await fetch(
            `${window.GeneGlassConfig.apiBaseUrl}/auth/forgot-password`,
            {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify({
                    email: forgotEmail.value.trim(),
                }),
            }
        );

        const result = await response.json().catch(() => null);

        if (!response.ok) {
            throw new Error(result?.detail || "Unable to request a reset link.");
        }

        forgotSuccess.textContent =
            "If an account exists for this email, a reset link has been sent.";
        forgotSuccess.hidden = false;

    } catch (error) {
        forgotError.textContent =
            error.message === "Failed to fetch"
                ? "Cannot reach the GeneGlass server."
                : error.message;

        forgotError.classList.add("show");

    } finally {
        forgotButton.disabled = false;
        forgotButton.querySelector("span").textContent = "Send Reset Instructions";
    }
});

// ===============================
// RESET PASSWORD
// ===============================

resetPasswordForm.addEventListener("submit", async function (event) {
    event.preventDefault();

    resetError.classList.remove("show");
    resetSuccess.hidden = true;

    if (newResetPassword.value !== confirmResetPassword.value) {
        resetError.textContent = "Passwords do not match.";
        resetError.classList.add("show");
        return;
    }

    resetButton.disabled = true;
    resetButton.querySelector("span").textContent = "Resetting...";

    try {
        const response = await fetch(
            `${window.GeneGlassConfig.apiBaseUrl}/auth/reset-password`,
            {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify({
                    token: resetToken.value.trim(),
                    new_password: newResetPassword.value
                })
            }
        );

        const result = await response.json().catch(() => null);

        if (!response.ok) {
            throw new Error(
                result?.detail || "Unable to reset password."
            );
        }

        resetSuccess.textContent =
            "Password reset successfully! You can now sign in.";

        resetSuccess.hidden = false;
        resetPasswordForm.reset();

        setTimeout(() => {
            openLoginForm();
        }, 2000);

    } catch (error) {
        resetError.textContent =
            error.message === "Failed to fetch"
                ? "Cannot reach the GeneGlass server."
                : error.message;

        resetError.classList.add("show");

    } finally {
        resetButton.disabled = false;
        resetButton.querySelector("span").textContent = "Reset Password";
    }
});

// ===============================
// SIGN UP
// ===============================

signupForm.addEventListener("submit", async function (event) {
    event.preventDefault();

    signupError.classList.remove("show");

    if (signupPassword.value !== confirmPassword.value) {
        signupError.textContent = "Passwords do not match.";
        signupError.classList.add("show");
        return;
    }

    signupButton.disabled = true;
    signupButton.querySelector("span").textContent = "Creating account...";

    try {
        const response = await fetch(
            `${window.GeneGlassConfig.apiBaseUrl}/auth/register`,
            {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify({
                    full_name: signupName.value.trim(),
                    email: signupEmail.value.trim(),
                    password: signupPassword.value,
                }),
            }
        );

        if (!response.ok) {
            const error = await response.json().catch(() => null);

            const detail = Array.isArray(error?.detail)
                ? error.detail.map(item => item.msg).join(" ")
                : error?.detail;

            throw new Error(detail || "Unable to create account.");
        }

        const registeredUser = await response.json();

        signupSuccess.textContent =
            `Account created successfully for ${registeredUser.email}. You can now sign in.`;

        signupSuccess.hidden = false;

        emailInput.value = registeredUser.email;

        signupForm.reset();
       openLoginForm();

        signupSuccess.hidden = false;

    } catch (error) {
        signupError.textContent =
            error.message === "Failed to fetch"
                ? "Cannot reach the GeneGlass server. Make sure the backend is running."
                : error.message;

        signupError.classList.add("show");

    } finally {
        signupButton.disabled = false;
        signupButton.querySelector("span").textContent = "Create Account";
    }
});
