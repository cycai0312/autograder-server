const SwaggerParser = require("@apidevtools/swagger-parser");
SwaggerParser.validate('autograder/rest_api/schema/schema.yml', (err, api) => {
  if (err) {
    console.error(err);
  }
  else {
    console.log("Schema validated successfully. API name: %s, Version: %s", api.info.title, api.info.version);
  }
});
