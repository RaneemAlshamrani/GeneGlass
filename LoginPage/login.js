const loginForm = document.getElementById("loginForm");
const togglePassword = document.getElementById("togglePassword");
const passwordInput = document.getElementById("password");
const emailInput = document.getElementById("email");
const rememberInput = document.getElementById("remember");
const errorMessage = document.getElementById("errorMessage");
const submitButton = loginForm.querySelector('button[type="submit"]');


// ===============================
// SHOW / HIDE PASSWORD
// ===============================

togglePassword.addEventListener("click", function () {

    if (passwordInput.type === "password") {
        passwordInput.type = "text";
    } else {
        passwordInput.type = "password";
    }

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
                headers: { "Content-Type": "application/x-www-form-urlencoded" },
                body,
            },
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
