(() => {
  const deleteModal = document.getElementById("deleteModal");
  if (!deleteModal) return;

  deleteModal.addEventListener("show.bs.modal", (event) => {
    const button = event.relatedTarget;
    if (!button) return;

    const dsid = button.getAttribute("data-dsid");
    const dsname = button.getAttribute("data-dsname");

    const nameEl = deleteModal.querySelector("#modalDsName");
    const formEl = deleteModal.querySelector("#deleteForm");

    if (nameEl) nameEl.textContent = dsname || "-";
    if (formEl) formEl.action = `/delete/${dsid}`;
  });
})();
