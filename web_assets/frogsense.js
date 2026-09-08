let mediaRecorder;
let audioChunks = [];

const recordBtn = document.getElementById("recordBtn");
const stopBtn = document.getElementById("stopBtn");

if (recordBtn)
  recordBtn.onclick = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      console.log("Mic access granted");
        mediaRecorder = new MediaRecorder(stream);
        audioChunks = [];

        mediaRecorder.ondataavailable = e => audioChunks.push(e.data);

        mediaRecorder.onstop = () => {
          const blob = new Blob(audioChunks, { type: "audio/webm" });
          const audioURL = URL.createObjectURL(blob);
          document.getElementById("playback").src = audioURL;

          uploadAudio(blob);
        };

        mediaRecorder.start();
        recordBtn.disabled = true;
        stopBtn.disabled = false;

    } catch (err) {
      console.error("Mic error:", err);
      alert(`${err.name}: ${err.message}`);
    }

  };

if (stopBtn)
    stopBtn.onclick = () => {
    mediaRecorder.stop();
    recordBtn.disabled = false;
    stopBtn.disabled = true;
  };

async function uploadAudio(blob) {
  const formData = new FormData();
  formData.append("audio", blob, "recording.webm");
  formData.append('type', 'audio');

  const response = await fetch(BASEURL + "/api/observation", {
    method: "POST",
    body: formData
  });

  const { id } = await response.json()
  poll(id)  
}

async function poll(id) {
  const res = await fetch(BASEURL + `/status/${id}`);
  const data = await res.json();

  if (data.status === "done") {
    showToast(data.text);
    loadRecent()
  } else {
    setTimeout(() => poll(id), 1000);
  }
}

function showToast(text) {
  const div = document.createElement("div");
  div.className = "toast";
  div.innerHTML = text;
  document.body.appendChild(div);

  setTimeout(() => div.remove(), 5000);
}

async function uploadAttachment() {
    const file = document.getElementById("attachment_file").files[0];
    const observationId = document.getElementById("attachment_observation_id").value;

    if (!file)
        return;

    const data = new FormData();
    data.append("file", file);

    const response = await fetch(BASEURL + "/api/observation/" + observationId + "/attachments", {
        method: "POST",
        body: data
    });

    if (!response.ok) {
        // bitch appropriately
        return;
    }

    await updateAttachmentList(observationId)
}

async function deleteAttachment(oid,aid) {
    if (!confirm("Really delete this attachment?"))
        return;

    const response = await fetch(BASEURL + `/api/observation/${oid}/attachment/${aid}`, {
        method: "DELETE"
    });

    await updateAttachmentList(oid)
}

async function updateAttachmentList(observationId) {

    const res = await fetch(BASEURL + "/api/observation/"+observationId+"/attachments");
    const data = await res.json();

    const container = document.getElementById("attachment_list");
    container.innerHTML = "";

  data.attachments.forEach(entry => {
    const div = document.createElement("div");
    var r = ""
    if (entry.icon != null)
        r += `${entry.icon} ${entry.formatted} `

    div.className = "entry";
    div.innerHTML = `
      <div>
    <a href="#" onclick="deleteAttachment('${data.observation_id}','${entry.attachment_id}')">🗑️</a> <a target="_blank" href="${BASEURL}/api/observation/${data.observation_id}/attachment/${entry.attachment_id}">${entry.name}</a> (${entry.length_formatted}; ${entry.mime_type})
      </div>
    `;
    container.appendChild(div);
  });
  
  if (data.attachments.length == 0)
    container.innerHTML = "<i>none</i>";
}

async function updateObservation(id, m) {
    try {
        const res = await fetch(BASEURL + "/api/observation/" + id, {
              method: "PATCH",
              headers: {
                "Content-Type": "application/json"
              },
              body: JSON.stringify({ field: m, value: document.getElementById(id + "_" + m).value})
            });
        console.log(res); // Process data
        await loadRecent();
    } catch (error) {
        console.error(error); // Handle errors
    }  
}

async function showAttachments(observationId) {
    document.getElementById("attachment_observation_id").value = observationId;
    document.getElementById("attachment_observation_text").innerHTML = new Date(document.getElementById(observationId + "_ts").value).toLocaleString() + "<br>" + document.getElementById(observationId + "_blurb").innerHTML
    await updateAttachmentList(observationId);
    document.getElementById("attachments").showModal();
}

async function loadRecent() {
  const res = await fetch(BASEURL + "/api/observations/recent");
  const data = await res.json();

  const container = document.getElementById("recent");
  container.innerHTML = "";

  data.forEach(entry => {
    const div = document.createElement("div");
    var r = ""
    if (entry.icon != null)
        r += `${entry.icon} ${entry.formatted} `

    div.className = "entry";
    div.innerHTML = `
      <div>
    <a href="#" onclick="deleteObservation('${entry.id}')">🗑️</a> 
    <!-- 🕒 --><form style="display: inline" onSubmit="updateObservation('${entry.id}', 'ts'); return false"><input onfocus="this.dataset.original=this.value" onblur="if (this.value !== this.dataset.original) this.form.requestSubmit()" style="display: inline" type="datetime-local" id="${entry.id}_ts" value="${entry.timestamp}"></form>
      &#128211; <span id="${entry.id}_blurb">${entry.subject} ${r}</span>
<span onclick="showAttachments('${entry.id}')">📎</span>
<span class="raw-observation">
    <input type="checkbox" id="${entry.id}_message_cb" class="raw-toggle">
    <label for="${entry.id}_message_cb">💬</label>
    <form class="raw-input" id="style="display: inline" onSubmit="updateObservation('${entry.id}', 'message'); return false"><input id="${entry.id}_message" value="${entry.message}"></form>
</span>
      </div>
    `;
    // 
    container.appendChild(div);
  });
}

async function deleteObservation(id) {
    if (!confirm("Really delete this observation?"))
        return;

    const response = await fetch(BASEURL + `/api/observation/${id}`, {
        method: "DELETE"
    });

    await loadRecent();
}

if (document.getElementById('recent'))
  loadRecent();

if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register(BASEURL + '/web_assets/sw.js')
    .then(reg => console.log('SW registered', reg))
    .catch(err => console.error('SW registration failed', err));
}

setTimeout(() => {{
    const t = document.getElementById("toast");
    if (t) t.style.display = "none";
}}, 5000);