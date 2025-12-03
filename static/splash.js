window.addEventListener("load", function() {
  const splash = document.getElementById("splash");
  const main = document.getElementById("main-content");

  setTimeout(() => {
    splash.style.display = "none";
    main.style.opacity = 1;
  }, 2000); // splash lasts 2 seconds
});
