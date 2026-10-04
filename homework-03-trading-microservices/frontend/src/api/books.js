import { deleteJson, getJson, postJson, putJson } from './http.js'

const BASE = '/api/books'

export const getBooks = () => getJson(`${BASE}/books`).then((res) => res.books)

export const createBook = (book) => postJson(`${BASE}/books`, book)

export const updateBook = (bookId, book) => putJson(`${BASE}/books/${encodeURIComponent(bookId)}`, book)

export const deleteBook = (bookId) => deleteJson(`${BASE}/books/${encodeURIComponent(bookId)}`)
