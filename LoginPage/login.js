
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

function openLoginForm() {
    loginForm.hidden = false;
    signupForm.hidden = true;
    loginSwitch.hidden = false;

    loginHeader.querySelector("h1").textContent = "Welcome back";
    loginHeader.querySelector("p").textContent = "Sign in to your account";

    signupError.classList.remove("show");
}

function openSignupForm()  {
    loginForm.hidden = true;
    signupForm.hidden = false;
    loginSwitch.hidden = true;
    signupSuccess.hidden = true;

    loginHeader.querySelector("h1").textContent = "Create Account";
    loginHeader.querySelector("p").textContent =
        "Create your GeneGlass specialist account";

    signupError.classList.remove("show");
}

document.getElementById("showSignup").addEventListener("click", function (event) {
    event.preventDefault();
    openSignupForm();
});

document.getElementById("showLogin").addEventListener("click", function (event) {
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
