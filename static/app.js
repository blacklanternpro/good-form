(function () {
  function pickedIds() {
    return Array.prototype.map.call(
      document.querySelectorAll("input.pick:checked"),
      function (el) { return parseInt(el.getAttribute("data-id"), 10); }
    ).filter(function (n) { return !isNaN(n); });
  }

  function allIds() {
    return Array.prototype.map.call(
      document.querySelectorAll("input.pick"),
      function (el) { return parseInt(el.getAttribute("data-id"), 10); }
    ).filter(function (n) { return !isNaN(n); });
  }

  function setAll(on) {
    document.querySelectorAll("input.pick").forEach(function (el) {
      el.checked = on;
    });
  }

  async function downloadIds(ids) {
    if (!ids.length) {
      alert("No images selected.");
      return;
    }
    const res = await fetch("/api/download", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ids: ids }),
    });
    if (!res.ok) {
      const text = await res.text();
      alert("Download failed: " + text);
      return;
    }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    const disp = res.headers.get("Content-Disposition") || "";
    const match = /filename="?([^"]+)"?/.exec(disp);
    a.download = match ? match[1] : "goodform.zip";
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
    window.location.reload();
  }

  const selectAll = document.getElementById("select-all");
  const deselectAll = document.getElementById("deselect-all");
  const downloadSelected = document.getElementById("download-selected");
  const downloadAll = document.getElementById("download-all");
  if (selectAll) selectAll.addEventListener("click", function () { setAll(true); });
  if (deselectAll) deselectAll.addEventListener("click", function () { setAll(false); });
  if (downloadSelected) downloadSelected.addEventListener("click", function () { downloadIds(pickedIds()); });
  if (downloadAll) downloadAll.addEventListener("click", function () { downloadIds(allIds()); });

  document.querySelectorAll("input.source-enabled").forEach(function (cb) {
    cb.addEventListener("change", function () {
      const id = cb.getAttribute("data-id");
      fetch("/api/sources/" + id + "/enabled", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ enabled: cb.checked }),
      });
      document.querySelectorAll("input.source-enabled[data-id='" + id + "']").forEach(function (other) {
        other.checked = cb.checked;
      });
    });
  });
})();
