const loginForm = document.getElementById("loginForm");
const togglePassword = document.getElementById("togglePassword");
const passwordInput = document.getElementById("password");


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

loginForm.addEventListener("submit", function (event) {

    event.preventDefault();

    // مؤقتًا ننتقل مباشرة للـ Dashboard
    window.location.href = "../DashboardPage/dashboard.html";

});