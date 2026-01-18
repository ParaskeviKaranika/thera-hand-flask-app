//Chat Bot logic
//In this function we define the chatbot behavior and interaction with the user .
//We create the chatbot interface and handle user input and the bot's responses.


(function ( ){
    // ========= DOM elements =========
  const botToggle   = document.getElementById("thera-bot-toggle");
  const botWindow   = document.getElementById("thera-bot-window");
  const botClose    = document.getElementById("thera-bot-close");
  const msgContainer= document.getElementById("thera-bot-messages");
  const inputField  = document.getElementById("thera-bot-input");
  const sendBtn     = document.getElementById("thera-bot-send");
  const voiceBtn    = document.getElementById("thera-bot-voice");
  const voiceStatus = document.getElementById("thera-bot-voice-status");
  

  const PAGE_LANG = (document.documentElement.lang || "el").toLowerCase().startsWith("en")
  ? "en"
  : "el";

    // ========= Bot texts per language =========
  const BOT_TEXT = {
    el: {
      welcome: "Καλώς ήρθες στο TheraHand! 😊\nΠώς μπορώ να σε βοηθήσω;",
      fallback: "Δεν είμαι σίγουρος ότι κατάλαβα. Μπορείς να το ξαναπείς λίγο διαφορετικά; 😊"
    },
    en: {
      welcome: "Welcome to TheraHand! 😊\nHow can I help you?",
      fallback: "I'm not sure I understood. Can you rephrase it? 😊"
    }
  };


  if (!botToggle || !botWindow || !botClose || !msgContainer || !inputField || !sendBtn) {
      console.warn("TheraBot: missing DOM elements (widget not found on this page).");
      return;
    }
  // ===== Toast (welcome popup) =====
const toast = document.getElementById("thera-toast");
const toastText = document.getElementById("thera-toast-text");
const toastClose = document.getElementById("thera-toast-close");

let toastTimer = null;

function showToast(message, ms = 5000) {
  if (!toast || !toastText) return; // if its not appear in DOM just skip

  toastText.innerText = message;
  toast.classList.remove("thera-hidden");

  if (toastTimer) clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {
    toast.classList.add("thera-hidden");
  }, ms);
}

if (toastClose) {
  toastClose.addEventListener("click", () => {
    toast.classList.add("thera-hidden");
    if (toastTimer) clearTimeout(toastTimer);
  });
}


  // ========= Open/close widget =========
  botToggle.addEventListener("click", () => {
    botWindow.classList.toggle("bot-hidden");
    if (!botWindow.classList.contains("bot-hidden")) {
      inputField.focus();
    }
  });

  botClose.addEventListener("click", () => {
    botWindow.classList.add("bot-hidden");
  });

  // ========= Helper functions =========
  function addMessage(text, sender = "bot") {
    const row = document.createElement("div");
    row.className = "bot-message-row";

    const bubble = document.createElement("div");
    bubble.className = `bot-bubble ${sender}`;
    bubble.innerText = text;

    row.appendChild(bubble);
    msgContainer.appendChild(row);
    msgContainer.scrollTop = msgContainer.scrollHeight;
    saveChat();

  }

  const CHAT_KEY = `thera_bot_history_v1_${PAGE_LANG}`;


function saveChat() {
  //Keep only last 40 messages to limit storage size
  const rows = Array.from(msgContainer.querySelectorAll(".bot-bubble")).slice(-40);
  const history = rows.map(b => ({
    sender: b.classList.contains("user") ? "user" : "bot",
    text: b.innerText
  }));
  localStorage.setItem(CHAT_KEY, JSON.stringify(history));
}
//Load chat history from localstorage
function loadChat() {
  const raw = localStorage.getItem(CHAT_KEY);
  if (!raw) return false;
  try {
    const history = JSON.parse(raw);
    if (!Array.isArray(history) || history.length === 0) return false;
    msgContainer.innerHTML = "";
    history.forEach(m => addMessage(m.text, m.sender));
    return true;
  } catch {
    return false;
  }
}

//Sanitize user input 
  function sanitize(text) {
    return (text || "").toString().trim();
  }
  if(!loadChat()){

  // ========= Initial message=========
  addMessage(BOT_TEXT[PAGE_LANG].welcome, "bot");

  }
  // ✅ Welcome toast only once per session
const WELCOME_TOAST_KEY = `thera_welcome_toast_seen_${PAGE_LANG}`;

if (!sessionStorage.getItem(WELCOME_TOAST_KEY)) {
  showToast(BOT_TEXT[PAGE_LANG].welcome, 600000);
  sessionStorage.setItem(WELCOME_TOAST_KEY, "1");
}

  // ========= Handle user message =========
  function handleUserMessage() {
    const text = sanitize(inputField.value);
    if (!text) return;

    addMessage(text, "user");
    inputField.value = "";

    const reply = getBotResponse(text);
    // Simulate typing delay
    setTimeout(() => addMessage(reply, "bot"), 300);
  }

  sendBtn.addEventListener("click", handleUserMessage);

  inputField.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      handleUserMessage();
    }
  });//create const variable to store questions and answers
const knowledgeBase = [
  {
    keywords: {
      el: ["πώς","πως","να","κάνω","κανω","άσκηση","ασκηση","1","ένα","ενα"],
      en: ["how","start","do","exercise","1","one","begin"]
    },
    answer: {
      el: "Τέλεια ,θα σε βοηθήσω για να ξεκινήσεις την άσκηση 1.Αρχικά θα πρέπει να διαβάσεις τις οδηγίες οι οποίες δίνονται πριν το κουμπί Συνέχεια μετά πατώντας το κουμπί περιμένεις λίγα δευτερόλεπτα και θα ανοίξει το παράθυρο για την άσκηση .Θα ανοίξει η κάμερα και κρατώντας μία απόσταση θα μπορείς να παίξεις το παιχνίδι "
        + " Θές να σου κάνω μια περιγραφή για το ποια κίνηση θα πρέπει να κάνεις με το χέρι είτε το αριστερό είτε το δεξί ?"
        + "Θές να σου εξηγήσω την άσκηση 1?",
      en: "Great! I’ll help you start Exercise 1. First, read the instructions shown before the Continue button. Then press Continue, wait a few seconds, and the exercise window will open. The camera will turn on, and by keeping a small distance you will be able to play the game. Would you like me to describe the hand movement (left or right hand)? Do you want me to explain Exercise 1?"
    }
  },
  {
    keywords: {
      el: ["πως","πώς","να","κάνω","κανω","την","κίνηση","κινηση","ποιά","ποια","για","άσκηση","ασκηση","1"],
      en: ["what","movement","gesture","hand","do","exercise","1","one","how"]
    },
    answer: {
      el: "Βεβαίως ! Θα σε βοηθήσω να καταλάβεις ακριβώς ποια κίνηση θα πρέπει να κάνεις για την άσκηση 1."
        + "Η άσκηση 1 σου ζητάει να ανοίγεις και να κλείνεις την παλάμη του χεριού σου αργά πάνω από κάθε αστέρι που βλέπεις στην οθόνη,"
        + "σκέψου ότι η κίνηση αυτή είναι περίπου σαν να χαιρετάς κάποιον κάνοντας την κίνηση εννοόντας ΄γεια τα λέμε'."
        + "Πρόσεξε δεν κλείνει και ο αντίχειρας μαζί με τα υπόλοιπα δάχτυλα ,αλλά παραμένει ανοιχτός προς τα έξω."
        + "Ελπίζω να βοήθησα!!!",
      en: "Of course! I’ll help you understand exactly what movement you need for Exercise 1. Exercise 1 asks you to slowly open and close your palm over each star you see on the screen. Think of it like a friendly wave—like saying “see you!”. Important: the thumb should NOT close together with the other fingers; it stays open/outwards. I hope this helps!"
    }
  },
  {
    keywords: {
      el: ["τι","κάνω","κανω","στην","άσκηση","ασκηση","1","ένα","ενα"],
      en: ["what","do","in","exercise","1","one","play","how"]
    },
    answer: {
      el: "Τέλεια ,θα σε βοηθήσω να καταλάβεις πως θα παίξεις την άσκηση 1."
        + "Στην άσκηση 1 ,όταν ανοίξει το παράθυρο εμφανίζεται ένας ουρανός με αστέρια ,"
        + "κάθε φορά θα ανοιγοκλείνεις την παλάμη σου αργά πάνω από κάθε αστέρι και μετά το σκόρ στα αριστερά θα αυξάνεται."
        + "Κάθε φορά θα κινείς το χέρι σου προς το κάθε αστέρι που θα θέλεις να 'πιάσεις' στην οθόνη."
        + "Θα πρέπει να πιάσεις δέκα αστέρια για να νικήσεις αλλιώς θα εμφανιστεί μήνυμα λάθους και θα μπορείς είτε να ξεκινήσεις ξανά την άσκηση,"
        + "είτε να επιστρέψεις στα στατιστικά ,στο μενού ή όπου αλλού θέλεις."
        + "Προσπάθησε να μην πιέζεις τον ευατό σου ώστε να πετύχεις το σκόρ ,κάνε ενδιάμεσα διαλείμματα έαν νιώθεις ενόχληση ή κόπωση.",
      en: "Great! Here is how to play Exercise 1. When the window opens, you will see a sky with stars. Slowly open and close your palm over each star, and your score on the left will increase. Move your hand toward the star you want to “catch” on the screen. You need to catch 10 stars to win; otherwise, an error message will appear and you can either restart the exercise or return to Statistics, the menu, or anywhere else. Try not to push yourself—take short breaks if you feel discomfort or fatigue."
    }
  },

  {
    keywords: {
      el: ["πώς","πως","να","κάνω","κανω","άσκηση","ασκηση","2","δύο","δυο"],
      en: ["how","start","do","exercise","2","two","begin"]
    },
    answer: {
      el: "Τέλεια ,θα σε βοηθήσω για να ξεκινήσεις την άσκηση 2.Αρχικά θα πρέπει να διαβάσεις τις οδηγίες οι οποίες δίνονται πριν το κουμπί Συνέχεια μετά πατώντας το κουμπί περιμένεις λίγα δευτερόλεπτα και θα ανοίξει το παράθυρο για την άσκηση .Θα ανοίξει η κάμερα και κρατώντας μία απόσταση θα μπορείς να παίξεις το παιχνίδι "
        + " Θές να σου κάνω μια περιγραφή για το ποια κίνηση θα πρέπει να κάνεις με το χέρι είτε το αριστερό είτε το δεξί ?"
        + "Θές να σου εξηγήσω την άσκηση 2?",
      en: "Great! I’ll help you start Exercise 2. First, read the instructions shown before the Continue button. Then press Continue, wait a few seconds, and the exercise window will open. The camera will turn on, and by keeping a small distance you will be able to play the game. Would you like me to describe the required hand movement (left or right hand)? Do you want me to explain Exercise 2?"
    }
  },
  {
    keywords: {
      el: ["πως","πώς","να","κάνω","κανω","την","κίνηση","κινηση","ποιά","ποια","για","άσκηση","ασκηση","2","δύο","δυο"],
      en: ["what","movement","gesture","hand","do","exercise","2","two","how"]
    },
    answer: {
      el: "Βεβαίως ! Θα σε βοηθήσω να καταλάβεις ακριβώς ποια κίνηση θα πρέπει να κάνεις για την άσκηση 2."
        + "Η άσκηση 2 σου ζητάει να πιάσεις κάποια σχήματα που θα εμφανιστούν στην οθόνη και να τα μετακινήσεις στο περίγραμμα το πράσινο που υπάρχει στα αριστερά"
        + "Η κίνηση για να πιάσεις τα σχήματα ,είναι το κλείσιμο όλων των δακτύλων σαν να πας να πιάσεις κάτι αρκετά μικρό για παράδειγμα ένα μικρό κυβάκι ,έτσι θα πιάσεις τα σχήματα αλλά το χέρι να δείχνει προς το κινητό σαν να πάς να πιάσεις κάτι προς την οθόνη."
        + "Ελπίζω να βοήθησα!!!",
      en: "Of course! I’ll help you understand exactly what movement you need for Exercise 2. Exercise 2 asks you to grab shapes that appear on the screen and move them into the green outline on the left. To grab a shape, close your fingers as if you’re picking up something small (for example, a tiny cube). Also, keep your hand facing the phone/screen, as if you are grabbing something toward the display. I hope this helps!"
    }
  },
  {
    keywords: {
      el: ["τι","κάνω","κανω","στην","άσκηση","ασκηση","2","δύο","δυο"],
      en: ["what","do","in","exercise","2","two","play","how"]
    },
    answer: {
      el: "Τέλεια ,θα σε βοηθήσω να καταλάβεις πως θα παίξεις την άσκηση 2."
        + "Στην άσκηση 2 ,θα πρέπει να μεταφέρεις τα σχήματα που βλέπεις στα δεξιά σου στην οθόνη στο περίγραμμα που φαίνεται στα αριστερά,"
        + "κάθε φορά που τοποθετείς ένα σχήμα μέσα στο περίγραμμα αυτό γίνεται πιο έντονο.Υπάρχει σκορ όπως και στις άλλες ασκήσεις και 60 δευτερόλεπτα για να νικήσεις.Αντίστοιχα εάν δεν πετύχεις το σκορ που χρειάζεται τότε μπορείς να ξανά παίξεις το παιχνίδι είτε να πατήσεις έξοδο και μετά να δείς τα στατιστικά."
        + "Προσπάθησε να μην πιέζεις τον ευατό σου ώστε να πετύχεις το σκόρ ,κάνε ενδιάμεσα διαλείμματα έαν νιώθεις ενόχληση ή κόπωση.",
      en: "Great! Here is how to play Exercise 2. You must move the shapes you see on the right side of the screen into the outline on the left. Each time you place a shape inside the outline, the outline becomes more intense/thicker. There is a score like the other exercises, and you have 60 seconds to win. If you don’t reach the required score, you can replay the game or press Exit and then view your statistics. Try not to push yourself—take short breaks if you feel discomfort or fatigue."
    }
  },

  {
    keywords: {
      el: ["πώς","πως","να","κάνω","κανω","άσκηση","ασκηση","3","τρία","τρια"],
      en: ["how","start","do","exercise","3","three","begin"]
    },
    answer: {
      el: "Τέλεια ,θα σε βοηθήσω για να ξεκινήσεις την άσκηση 3.Αρχικά θα πρέπει να διαβάσεις τις οδηγίες οι οποίες δίνονται πριν το κουμπί Συνέχεια μετά πατώντας το κουμπί περιμένεις λίγα δευτερόλεπτα και θα ανοίξει το παράθυρο για την άσκηση .Θα ανοίξει η κάμερα και κρατώντας μία απόσταση θα μπορείς να παίξεις το παιχνίδι "
        + " Θές να σου κάνω μια περιγραφή για το ποια κίνηση θα πρέπει να κάνεις με το χέρι είτε το αριστερό είτε το δεξί ?"
        + "Θές να σου εξηγήσω την άσκηση 3?",
      en: "Great! I’ll help you start Exercise 3. First, read the instructions shown before the Continue button. Then press Continue, wait a few seconds, and the exercise window will open. The camera will turn on, and by keeping a small distance you will be able to play the game. Would you like me to describe the required hand movement (left or right hand)? Do you want me to explain Exercise 3?"
    }
  },
  {
    keywords: {
      el: ["πως","πώς","να","κάνω","κανω","την","κίνηση","κινηση","ποιά","ποια","για","άσκηση","ασκηση","τρία","3","τρια"],
      en: ["what","movement","gesture","hand","do","exercise","3","three","how"]
    },
    answer: {
      el: "Βεβαίως ! Θα σε βοηθήσω να καταλάβεις ακριβώς ποια κίνηση θα πρέπει να κάνεις για την άσκηση 3."
        + "Η άσκηση 3 σου ζητάει  να παίξεις ενα παιχνίδι όπως ακριβώς λειτουργεί ένα sliding puzzle ."
        + "Κάθε φορά θα πρέπει να μετακινήσεις το κενό κουτί στο παζλ προς το κίτρινο κουτί.Κάθε φορά που θα μετακινείς 5 φορές οτ κενό κουτι στην θέση του κίτρινου ,θα πηγαίνεις στο επόμενο επίπεδο"
        + "Η κίνηση που χρειάζεται να κάνεις ώστε να μεταφέρεις το κενό στο κίτρινο είνσι να κλείνεις τον δείκτη και τον αντίχειρα μεταξύ τους ,δηλαδή να ακουμπάς τις κορυφές των δακτύλων μεταξύ τους "
        + "Ελπίζω να βοήθησα!!!",
      en: "Of course! I’ll help you understand exactly what movement you need for Exercise 3. Exercise 3 is like a sliding puzzle game. Each time, you must move the empty box in the puzzle toward the yellow box. Every time you move the empty box onto the yellow position 5 times, you go to the next level. The gesture you need is to touch the tip of your index finger and the tip of your thumb together (like pinching / the “OK” fingertip contact). I hope this helps!"
    }
  },
  {
    keywords: {
      el: ["τι","κάνω","κανω","στην","άσκηση","ασκηση","3","τρία","τρια"],
      en: ["what","do","in","exercise","3","three","play","how"]
    },
    answer: {
      el: "Τέλεια ,θα σε βοηθήσω να καταλάβεις πως θα παίξεις την άσκηση 3."
        + "Στην άσκηση 3 , θα πρέπει να μετακινείς το κενό κουτί στο παζλ προς την θέση του κίτρινου μέχρι να βρεθεί πάνω στο κίτρινο.Στην συνέχεια το κίτρινο κουτί θααλλάζει θέσεις στο παζλ κάθε φορά που θα πηγαίνεις με το κενό κουτί πάνω του .Μετά θα πηγαίνεις στο επόμενο επίπεδο."
        + "Προσπάθησε να μην πιέζεις τον ευατό σου ώστε να πετύχεις το σκόρ ,κάνε ενδιάμεσα διαλείμματα έαν νιώθεις ενόχληση ή κόπωση.",
      en: "Great! Here is how to play Exercise 3. You must move the empty box in the puzzle to the position of the yellow box until it lands on it. Then the yellow box changes position each time you reach it with the empty box. After that, you move on to the next level. Try not to push yourself—take short breaks if you feel discomfort or fatigue."
    }
  },

  {
    keywords: {
      el: ["πώς","πως","να","κάνω","κανω","άσκηση","ασκηση","4","τέσσερα","τεσσερα"],
      en: ["how","start","do","exercise","4","four","begin"]
    },
    answer: {
      el: "Τέλεια ,θα σε βοηθήσω για να ξεκινήσεις την άσκηση 4.Αρχικά θα πρέπει να διαβάσεις τις οδηγίες οι οποίες δίνονται πριν το κουμπί Συνέχεια μετά πατώντας το κουμπί περιμένεις λίγα δευτερόλεπτα και θα ανοίξει το παράθυρο για την άσκηση .Θα ανοίξει η κάμερα και κρατώντας μία απόσταση θα μπορείς να παίξεις το παιχνίδι "
        + " Θές να σου κάνω μια περιγραφή για το ποια κίνηση θα πρέπει να κάνεις με το χέρι είτε το αριστερό είτε το δεξί ?"
        + "Θές να σου εξηγήσω την άσκηση 4?",
      en: "Great! I’ll help you start Exercise 4. First, read the instructions shown before the Continue button. Then press Continue, wait a few seconds, and the exercise window will open. The camera will turn on, and by keeping a small distance you will be able to play. Would you like me to describe the required hand movement (left or right hand)? Do you want me to explain Exercise 4?"
    }
  },
  {
    keywords: {
      el: ["πως","πώς","να","κάνω","κανω","την","κίνηση","κινηση","ποιά","ποια","για","άσκηση","ασκηση","4","τέσσερα","τεσσερα"],
      en: ["what","movement","gesture","hand","do","exercise","4","four","how"]
    },
    answer: {
      el: "Βεβαίως! Η άσκηση 4 είναι η πιο απαιτητική γιατί διαρκεί περισσότερα λεπτά. "
        + "Μέσα στην άσκηση, στην οθόνη, θα δεις επάνω αριστερά μια φωτογραφία/οδηγό με την κίνηση που πρέπει να κάνεις ώστε να την εκτελέσεις σωστά. "
        + "Ακολούθησε τη φωτογραφία βήμα-βήμα και κάνε μικρά διαλείμματα αν νιώσεις κούραση ή ενόχληση."
        + "Ελπίζω να βοήθησα!!!",
      en: "Of course! Exercise 4 is the most demanding because it lasts more minutes. During the exercise, on the screen (top-left) you will see a guide image showing the movement you need to perform correctly. Follow the image step by step and take small breaks if you feel tired or uncomfortable. I hope this helps!"
    }
  },

  {
    keywords: {
      el: ["πως","πώς","να","αλλάξω","αλλαξω","κωδικό","κωδικο"],
      en: ["how","change","password","reset","update","my"]
    },
    answer: {
      el: "Ναι ,θα σε βοηθήσω να αλλάξεις κωδικό.Στην οθόνη σου  πάνω αριστερά  βρίσκεται ένα κουμπί που όταν το πατήσεις θα σε ανακατυεθύνει στο προφίλ."
        + "Στο κάτω μέρος της σελίδας υπάρχει η διαχείριση στο προφίλ όπου μπορείς να αλλάξεις τον κωδικό,θα σε ανακατευθύνει σε μια σελίδα όπου θα γίνει αλλαγή και συην συνέχεια θα λάβεις email επιβεβαίωσης στο email που έχεις συμπληρώσει."
        + "Εάν χρειάζεσαι βοήθεια σε κάτι άλλο είτε για τις ασκήσεις είτε για ρυθμίσεις της εφαρμογής ,είμαι εδώ να βοηθήσω!!!",
      en: "Yes, I can help you change your password. On the top-left of the screen there is a button that takes you to your Profile. At the bottom of the profile page, you will find Profile Management where you can change your password. You will be redirected to a page to set the new password, and then you’ll receive a confirmation email to the email you used. If you need help with anything else (exercises or app settings), I’m here to help!"
    }
  },

  {
    keywords: {
      el: ["προφίλ","προφιλ","να","ανοίξω","ανοιξω","profile","που","βρίσκεται","βρισκεται"],
      en: ["profile","open","where","is","located","account"]
    },
    answer: {
      el: "Βεβαίως! Για να ανοίξεις το προφίλ σου:"
        + " Στην πάνω μπάρα της εφαρμογής, πάτησε το εικονίδιο χρήστη που βρίσκεται πάνω αριστερά."
        + " Εκεί θα δεις την «Διαχείριση Προφίλ» με επιλογές όπως Επεξεργασία Προφίλ και Αλλαγή Κωδικού."
        + " Θες να σου πω και πώς αλλάζεις φωτογραφία προφίλ;",
      en: "Sure! To open your profile: In the top bar of the app, tap the user icon on the top-left. There you will see “Profile Management” with options like Edit Profile and Change Password. Do you want me to tell you how to change your profile picture too?"
    }
  },
  {
    keywords: {
      el: ["επεξεργασία","επεξεργασια","προφίλ","προφιλ","αλλαγές","αλλαγες","στοιχεία","στοιχεια"],
      en: ["edit","profile","change","details","information","update"]
    },
    answer: {
      el: "Για να κάνεις αλλαγές στο προφίλ σου:"
        + " 1) Πάτησε το εικονίδιο χρήστη πάνω αριστερά για να μπεις στο προφίλ."
        + " 2) Στην ενότητα «Διαχείριση Προφίλ» πάτησε «Επεξεργασία Προφίλ»."
        + " 3) Κάνε τις αλλαγές που θέλεις και μετά πάτησε αποθήκευση.",
      en: "To change your profile details: 1) Tap the user icon on the top-left to open your profile. 2) In “Profile Management”, tap “Edit Profile”. 3) Make your changes and then tap Save."
    }
  },
  {
    keywords: {
      el: ["φωτογραφία","φωτογραφια","avatar","εικόνα","εικονα","αλλάξω","αλλαξω","προφίλ","προφιλ"],
      en: ["change","photo","picture","avatar","profile","image"]
    },
    answer: {
      el: "Ναι! Για να αλλάξεις φωτογραφία (avatar) στο προφίλ:"
        + " 1) Άνοιξε το προφίλ από το εικονίδιο χρήστη πάνω αριστερά."
        + " 2) Πάτησε το εικονίδιο +."
        + " 3) Επίλεξε/ανέβασε νέα φωτογραφία και πάτησε αποθήκευση."
        + " Μετά η φωτογραφία θα φαίνεται και πάνω αριστερά στη μπάρα.",
      en: "Yes! To change your profile photo (avatar): 1) Open your profile from the user icon on the top-left. 2) Tap the + icon. 3) Select/upload a new photo and tap Save. After that, the photo will also appear on the top-left of the bar."
    }
  },
  {
    keywords: {
      el: ["dark","light","θέμα","θεμα","αλλάζω","αλλαζω","κουμπί","κουμπι","πάνω","δεξιά","δεξια","σελήνη","σεληνη"],
      en: ["dark","light","theme","toggle","moon","top","right"]
    },
    answer: {
      el: "Για να αλλάξεις θέμα (Dark / Light):"
        + " Πάτησε το κουμπί 🌓 που βρίσκεται πάνω δεξιά στη μπάρα."
        + " Με ένα πάτημα γίνεται αλλαγή από Dark σε Light (ή το αντίστροφο).",
      en: "To change theme (Dark / Light): Tap the 🌓 button at the top-right of the bar. With one tap it switches between Dark and Light."
    }
  },
  {
    keywords: {
      el: ["αποσύνδεση","αποσυνδεση","logout","έξοδος","εξοδος","να","βγω","βγει","λογαριασμό","λογαριασμο"],
      en: ["logout","log","out","sign","out","exit","account"]
    },
    answer: {
      el: "Για να αποσυνδεθείς από τον λογαριασμό σου:"
        + " 1) Μπες στο προφίλ από το εικονίδιο χρήστη πάνω αριστερά."
        + " 2) Στη «Διαχείριση Προφίλ» θα βρεις την επιλογή αποσύνδεσης (ή έξοδο)."
        + " 3) Όταν πατήσεις αποσύνδεση, θα σου εμφανιστεί μήνυμα επιβεβαίωσης (Ναι/Όχι).",
      en: "To log out of your account: 1) Open your profile from the user icon on the top-left. 2) In “Profile Management” you will find the Log out (or Exit) option. 3) When you press Log out, a confirmation message will appear (Yes/No)."
    }
  },
  {
    keywords: {
      el: ["στατιστικά","στατιστικα","export","pdf","αναφορά","αναφορα","εκτύπωση","εκτυπωση","κατέβασμα","κατεβασμα"],
      en: ["stats","statistics","export","pdf","report","download","print"]
    },
    answer: {
      el: "Για Export PDF από τα Στατιστικά:"
        + " 1) Πήγαινε στη σελίδα «Στατιστικά»."
        + " 2) Πάτησε το κουμπί «Export PDF»."
        + " 3) Θα ανοίξει ένα παράθυρο που ζητάει Όνομα και Επώνυμο για να μπουν στο PDF."
        + " 4) Πάτησε «Δημιουργία PDF» και θα γίνει λήψη της αναφοράς."
        + " Αν δεν βλέπεις το κουμπί Export, σημαίνει ότι δεν υπάρχουν ακόμα στατιστικά.",
      en: "To Export a PDF from Statistics: 1) Go to the “Statistics” page. 2) Press the “Export PDF” button. 3) A window will open asking for First name and Last name to include in the PDF. 4) Press “Create PDF” and the report will be downloaded. If you don’t see the Export button, it means there are no statistics yet."
    }
  },
  {
    keywords: {
      el: ["όνομα","ονομα","επώνυμο","επωνυμο","να","μπαίνει","μπαινει","αυτόματα","αυτοματως","στο","pdf","αποθήκευση","αποθηκευση"],
      en: ["name","surname","last","first","automatic","auto","pdf","save"]
    },
    answer: {
      el: "Για να μπαίνουν αυτόματα Όνομα/Επώνυμο στο PDF:"
        + " 1) Πάτησε Export PDF μία φορά."
        + " 2) Συμπλήρωσε Όνομα και Επώνυμο."
        + " 3) Από εδώ και πέρα, η εφαρμογή τα θυμάται και θα τα εμφανίζει έτοιμα στο παράθυρο του PDF."
        + " Αν θες, μπορείς να τα αλλάξεις οποιαδήποτε στιγμή ξανά μέσα από το Export PDF.",
      en: "To have First name/Last name filled automatically in the PDF: 1) Press Export PDF once. 2) Enter your First name and Last name. 3) From then on, the app remembers them and pre-fills them in the PDF window. If you want, you can change them anytime from the Export PDF window."
    }
  },
  {
    keywords: {
      el: ["ρυθμίσεις","ρυθμισεις","υπενθύμιση","υπενθυμιση","ώρα","ωρα","ενεργοποίηση","ενεργοποιηση"],
      en: ["settings","reminder","enable","time","notification","set"]
    },
    answer: {
      el: "Για την Υπενθύμιση (Ρυθμίσεις):"
        + " 1) Πήγαινε στις Ρυθμίσεις της εφαρμογής."
        + " 2) Επίλεξε «Ενεργοποίηση Υπενθύμισης: Ναι/Όχι»."
        + " 3) Ρύθμισε την «Ώρα Υπενθύμισης» και πάτησε «Αποθήκευση»."
        + " Αν θες, πες μου τι ώρα θέλεις και πόσες φορές την εβδομάδα για να σου προτείνω ρύθμιση.",
      en: "For Exercise Reminders (Settings): 1) Go to the app Settings. 2) Choose “Enable Reminder: Yes/No”. 3) Set the “Reminder Time” and press “Save”. If you want, tell me what time you prefer and how many times per week, and I can suggest a good setting."
    }
  },
  {
    keywords: {
      el: ["ευχαριστώ","ευχαριστω","πολύ","πολυ","σε"],
      en: ["thank","thanks","thankyou","ty"]
    },
    answer: {
      el: "Δεν κάνει τίποτα !!! Οτιδήποτε άλλο χρειάζεσαι είμαι εδώ για να σε βοηθήσω!",
      en: "You’re welcome! If you need anything else, I’m here to help!"
    }
  }
];

  
//Create const variable to store stop words for each language 
//As stop words we consider common words that do not add significant meaning to the text 
const stopWordsByLang = {
  el: new Set(["πώς","πως","να","κανω","κάνω","την","το","τι","σε","στο","για","με","και","ένα","ενα"]),
  en: new Set(["how","to","do","the","a","an","in","on","for","with","and","i","you","your"])
};
//Function to normalize text by converting to lowercase,remove diacritics and triming whitespaces
function normalize(s){
  return (s || "")
    .toLowerCase()
    .normalize("NFD").replace(/[\u0300-\u036f]/g, "")
    .trim();
}
//Function to score an item based on the presence of keywords in the user text
//The function returns the score as the number of matching keywords.
//It ignores stop words defined for each language .


function scoreItem(userText, item, lang){
  const t = normalize(userText);

  //Get keywords for the specified language or default to all keywords
  const keywords = item.keywords?.[lang] || item.keywords || [];

  const cleanedKeywords = keywords
    .map(normalize)
    .filter(kw => kw && !stopWordsByLang[lang].has(kw));

  let score = 0;
  for (const kw of cleanedKeywords) {
    if (t.includes(kw)) score++;
  }
  return score;
}
//Create const variable to store bot state
//The bot state includes whether it is awaiting hand selection and the last exercise discussed
//This state can be used to manage multi-turn conversations
//and provide context aware responses 
const botState={awaitingHand:false ,lastExercise:null};
//Functions to detect exercise number and hand from user text
//These functions look for specific keywords or numbers in the text
//and return the corresponding exercise number or hand side

function  detectExerciseNumber(t){
  if (t.includes("1") || t.includes("ενα") || t.includes("ένα")) return 1;
  if (t.includes("2") || t.includes("δυο") || t.includes("δύο")) return 2;
  if (t.includes("3") || t.includes("τρια") || t.includes("τρία")) return 3;
  if (t.includes("4") || t.includes("τεσσερα") || t.includes("τέσσερα")) return 4;
  return null;
}
function detectHand(t){
  if (t.includes("αριστερ")) return "αριστερό";
  if (t.includes("δεξι")) return "δεξί";
  return null;
}

  // ========= Bot logic =========
  //Function to sanitize user input by triming whitespace and converting to lowercase
  //This helps ensure consistent processing of user messages.
  //It can be extended to include more sanitization steps as needed.
  //Function to get bot response based on user input .
  function getBotResponse(rawText) {
  const text = sanitize(rawText);
  const lang = PAGE_LANG;

  let best = null;
  let bestScore = 0;

  for (const item of knowledgeBase) {
    const s = scoreItem(text, item, lang);
    if (s > bestScore) {
      bestScore = s;
      best = item;
    }
  }

  // if a good match is found score >=2 return the correspoding answer
  if (best && bestScore >= 2) {
    return best.answer?.[lang] || best.answer?.el || BOT_TEXT[lang].fallback;
  }

  return BOT_TEXT[lang].fallback;
}


// ========= Voice input =========

  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition || null;
//Set up voice input if supported by the browser
//This allows users to interact with the bot using speech 
//The voice input button starts/stops listening and processes the recognized speech
//to generate bot responses
  if (!SpeechRecognition) {
    voiceBtn.disabled = true;
    voiceBtn.title = "Ο περιηγητής σου δεν υποστηρίζει φωνητικές εντολές.";
  } else {
    const recognizer = new SpeechRecognition();
    recognizer.lang = (PAGE_LANG === "en") ? "en-US" : "el-GR";

    recognizer.continuous = false;
    recognizer.interimResults = false;

    let listening = false;

    voiceBtn.addEventListener("click", () => {
      if (!listening) {
        listening = true;
        voiceStatus.textContent = (PAGE_LANG === "en") ? "🎤 Speak now..." : "🎤 Μίλησε τώρα...";

        recognizer.start();
      } else {
        listening = false;
        voiceStatus.textContent = "";
        recognizer.stop();
      }
    });

    recognizer.onresult = (event) => {
      listening = false;
      voiceStatus.textContent = "";
      const transcript = event.results[0][0].transcript;
      inputField.value = transcript;
      handleUserMessage();
    };

    recognizer.onerror = () => {
      listening = false;
      voiceStatus.textContent = "Δεν κατάφερα να ακούσω καθαρά. Δοκίμασε ξανά ή γράψε το μήνυμα.";
    };

    recognizer.onend = () => {
      listening = false;
    };
  }
  
})()