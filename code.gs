function onGmailPage() {
  var startdateWidget = CardService.newDatePicker()
    .setTitle("Choose a start date")
    .setFieldName("startDate")
    .setValueInMsSinceEpoch(new Date().getTime());
    
  var enddateWidget = CardService.newDatePicker()
    .setTitle("Choose an end date")
    .setFieldName("endDate")
    .setValueInMsSinceEpoch(new Date().getTime());

  var applyButton =  CardService.newTextButton()
    .setText("Apply")
    .setOnClickAction(CardService.newAction()
    .setFunctionName("handleApply"));

  var submitButton = CardService.newTextButton()
    .setText("Submit")
    .setOnClickAction(CardService.newAction()
      .setFunctionName("handleSubmit"));

  var section = CardService.newCardSection()
    .addWidget(startdateWidget)
    .addWidget(enddateWidget)
    .addWidget(submitButton)
    .addWidget(CardService.newTextParagraph().setText("Maximum email limit: ~200"));

  var card = CardService.newCardBuilder()
    .setHeader(CardService.newCardHeader().setTitle("Welcome to Nico's Email Summarizer"))
    .addSection(CardService.newCardSection()
    .addWidget(CardService.newTextParagraph().setText("Select a start and end date of emails to summarise.")))
    .addSection(section)
    .build();

  return card;
}

function sendToLambdaAsync(payload) {
    var url = 'https://fkw6d1sbee.execute-api.us-east-1.amazonaws.com/default/gmail_summarise_addon';
    var options = {
        method: 'post',
        contentType: 'application/json',
        payload: payload,
        muteHttpExceptions: true
    };

    // Execute the URL Fetch call asynchronously
    UrlFetchApp.fetch(url, options);
}

function createProcessingCard() {
    var textToDisplay = "Process started. You should receive an email once the process is complete.";
    return CardService.newCardBuilder()
        .addSection(CardService.newCardSection()
            .addWidget(CardService.newTextParagraph().setText(textToDisplay))
        ).build();
}

function handleSubmit(e) {

  var startdateMs = e.formInput.startDate.msSinceEpoch;
  var startdate = new Date(startdateMs);
  var startdateiso = startdate.toISOString();

  var enddateMs = e.formInput.endDate.msSinceEpoch;
  var enddate = new Date(enddateMs);
  var enddateiso = enddate.toISOString();

  var scriptToken = ScriptApp.getOAuthToken();

  var payload = JSON.stringify({
  start_date: startdateiso,
  end_date: enddateiso,
  gmail_access_token: scriptToken
  });

  sendToLambdaAsync(payload);

  // Immediately update the UI after starting the process
  return createProcessingCard();
  console.log(payload)
}  
//   var response = UrlFetchApp.fetch('https://fkw6d1sbee.execute-api.us-east-1.amazonaws.com/default/gmail_summarise_addon', {
//     method: 'post',
//     contentType: 'application/json',
//     payload: payload,
//     muteHttpExceptions: true
//     });

//   textToDisplay = "Process started. You will receive an email once the process is complete."

//   return CardService.newCardBuilder()
//       .addSection(CardService.newCardSection()
//           .addWidget(CardService.newTextParagraph().setText(textToDisplay))
//       ).build();
// }