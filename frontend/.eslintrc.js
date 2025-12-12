module.exports = {
  env: {
    browser: true,
    es2021: true,
  },
  extends: ['plugin:react/recommended', 'standard-with-typescript', 'prettier'],
  overrides: [],
  parserOptions: {
    ecmaVersion: 'latest',
    sourceType: 'module',
    project: ['./tsconfig.json'],
  },
  plugins: ['react', 'unused-imports', 'prettier'],
  rules: {
    'prettier/prettier': ['error'],

    'no-restricted-imports': [
      'error',
      {
        patterns: [
          {
            group: ['./*', '../*'],
            message: 'Usage of relative parent imports is not allowed.',
          },
        ],
      },
    ],
    'react/jsx-no-undef': [0, { allowGlobals: true }],
    '@typescript-eslint/restrict-template-expressions': [0],
    '@typescript-eslint/strict-boolean-expressions': [0],
    'unused-imports/no-unused-imports': 'error',
    'unused-imports/no-unused-vars': [
      'warn',
      {
        vars: 'all',
        varsIgnorePattern: '^_',
        args: 'after-used',
        argsIgnorePattern: '^_',
      },
    ],
    'react/react-in-jsx-scope': 'off',
    'react/jsx-uses-react': 'off',
    'max-len': ['warning', { code: 250 }],
  },
};
