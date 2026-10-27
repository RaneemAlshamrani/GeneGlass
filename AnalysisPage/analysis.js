// Frontend-only file selection.
const fileInput = document.getElementById("ab1");
const fileInfo = document.getElementById("fileInfo");
const analyzeButton = document.getElementById("analyze");
const message = document.getElementById("message");

fileInput.addEventListener("change", () => {
  const file = fileInput.files && fileInput.files[0];
  if (!file) {
    fileInfo.textContent = "No file selected";
    analyzeButton.disabled = true;
    message.textContent = "";
    return;
  }
  if (!/\.ab1$/i.test(file.name)) {
    fileInfo.textContent = "Please select a .ab1 file.";
    analyzeButton.disabled = true;
    message.textContent = "";
    fileInput.value = "";
    return;
  }
  fileInfo.textContent = `Selected: ${file.name}`;
  analyzeButton.disabled = false;
  message.textContent = "";
});

analyzeButton.addEventListener("click", () => {
  if (!fileInput.files || !fileInput.files[0]) return;
  message.textContent = "File selected. Backend analysis is not connected yet.";
});
