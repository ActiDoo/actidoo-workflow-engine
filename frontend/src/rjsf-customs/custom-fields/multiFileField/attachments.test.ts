// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import {
  fileMatchesAccept,
  isAttachmentMultiSchema,
  isAttachmentSingleSchema,
  isRealFile,
} from './attachments';

describe('isRealFile', () => {
  it('rejects placeholder entries and empty values', () => {
    expect(isRealFile({})).toBe(false);
    expect(isRealFile(null)).toBe(false);
    expect(isRealFile(undefined)).toBe(false);
    expect(isRealFile({ datauri: '', filename: '', hash: null })).toBe(false);
  });

  it('accepts entries with any identifying property', () => {
    expect(isRealFile({ filename: 'a.pdf' })).toBe(true);
    expect(isRealFile({ datauri: 'data:image/png;base64,AAA' })).toBe(true);
    expect(isRealFile({ hash: 'abc' })).toBe(true);
    expect(isRealFile({ id: '42' })).toBe(true);
    expect(isRealFile({ mimetype: 'application/pdf' })).toBe(true);
  });
});

describe('isAttachmentSingleSchema', () => {
  it('recognizes the single attachment schema shape', () => {
    const schema = {
      type: 'object',
      properties: { datauri: { type: 'string', format: 'data-url' } },
    };

    expect(isAttachmentSingleSchema(schema)).toBe(true);
  });

  it('rejects other object schemas', () => {
    expect(isAttachmentSingleSchema({ type: 'object', properties: {} })).toBe(false);
    expect(
      isAttachmentSingleSchema({
        type: 'object',
        properties: { datauri: { type: 'string' } },
      })
    ).toBe(false);
    expect(isAttachmentSingleSchema(null)).toBe(false);
    expect(isAttachmentSingleSchema({ type: 'object', properties: [] })).toBe(false);
  });
});

describe('isAttachmentMultiSchema', () => {
  it('recognizes the multi attachment schema shape', () => {
    const schema = {
      type: 'array',
      items: {
        type: 'object',
        properties: { datauri: { type: 'string', format: 'data-url' } },
      },
    };

    expect(isAttachmentMultiSchema(schema)).toBe(true);
  });

  it('rejects other array schemas', () => {
    expect(isAttachmentMultiSchema({ type: 'array', items: { type: 'string' } })).toBe(false);
    expect(isAttachmentMultiSchema({ type: 'array', items: [{ type: 'string' }] })).toBe(false);
    expect(isAttachmentMultiSchema({ type: 'object' })).toBe(false);
    expect(isAttachmentMultiSchema(undefined)).toBe(false);
  });
});

describe('fileMatchesAccept', () => {
  it('matches extensions and mime types', () => {
    const file = (name: string, type: string) => ({ name, type });
    expect(fileMatchesAccept(file('report.PDF', 'application/pdf'), ['.pdf'])).toBe(true);
    expect(fileMatchesAccept(file('report.pdf.txt', 'text/plain'), ['.pdf'])).toBe(false);
    expect(fileMatchesAccept(file('a.png', 'image/png'), ['.pdf', 'image/*'])).toBe(true);
    expect(fileMatchesAccept(file('a.json', 'application/json'), ['application/json'])).toBe(true);
  });
});
