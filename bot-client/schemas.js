const { z } = require('zod');

const ActionSchema = z.object({
  action: z.string(),
  // Generic params as we have many actions with different params
  // Strict validation for each action type would be better, but for now we validate base structure
}).passthrough();

const BaseCommandSchema = z.object({
  action: z.string(),
});

module.exports = {
  validateCommand: (data) => {
    return BaseCommandSchema.safeParse(data);
  }
};
