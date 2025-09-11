# PAIPI Angular UI

This is the official web frontend for **PAIPI**, the AI-Powered PyPI Search engine. Built with Angular and styled with Tailwind CSS, this single-page application provides a clean and responsive interface to interact with the `paipi` backend, allowing you to search for Python packages, generate detailed README files, and download scaffolded package structures.

## Features

- **AI-Powered Search**: Leverage the knowledge of a Large Language Model to find Python packages based on natural language queries.
- **Package Validation**: Search results are color-coded to indicate whether a package name actually exists on the official PyPI repository.
- **Detailed Package View**: Click on any search result to see a clean, detailed view with metadata, project links, and keywords.
- **On-Demand README Generation**: With a single click, ask the AI to generate a comprehensive `README.md` file based on the package's metadata.
- **Package Scaffolding**: Download a functional, pre-structured `.zip` file for any generated package, complete with a `pyproject.toml` and the generated README.

## Prerequisites

Before you begin, ensure you have the following installed:

1. **Node.js**: A recent LTS version is recommended.
2. **Angular CLI**: Install it globally if you haven't already: `npm install -g @angular/cli`.
3. **Running PAIPI Backend**: This is a frontend application and **requires the Python backend to be running**. By default, it expects the backend to be available at `http://127.0.0.1:8080`.

## Getting Started

Follow these steps to get the application running on your local machine.

1. **Clone the repository:**

   ```bash
   git clone git@github.com:matthewdeanmartin/paipi.git
   cd paipi-app
   ```

2. **Install dependencies:**

   ```bash
   npm install
   ```

3. **Run the application:**

   ```bash
   ng serve
   ```

   Navigate to `http://localhost:4200/` in your browser. The application will automatically reload if you change any of the source files.

## How to Use the Application

1. **Search for Packages**: Use the main search bar to enter a query, like `http clients for python` or `terminal text editors`.
2. **View Results**: The application will display a list of packages found by the AI.
  - Package names in \<span style="color: \#60A5FA;"\>**blue**\</span\> exist on PyPI.
  - Package names in \<span style="color: \#F87171;"\>**red**\</span\> are AI-generated suggestions that do not exist on PyPI.
3. **See Details**: Click on any package to navigate to the detail view. Here you'll find the summary, description, author, license, and relevant links.
4. **Generate a README**: In the detail view, click the **"Generate README.md"** button. The application will send the package metadata to the backend, which uses the AI to generate and return a complete markdown file.
5. **Download the Package**: Once the README has been generated, a **"Download Package"** button will appear. Clicking this will generate and download a `.zip` archive containing a basic Python package structure (`pyproject.toml`, `__init__.py`, etc.) and the newly created README.

## How to Contribute

Contributions are what make the open-source community such an amazing place to learn, inspire, and create. Any contributions you make are **greatly appreciated**.

If you have a suggestion that would make this better, please fork the repo and create a pull request. You can also simply open an issue with the tag "enhancement".

1. **Fork the Project**
2. **Create your Feature Branch**
   ```bash
   git checkout -b feature/AmazingFeature
   ```
3. **Commit your Changes**
   ```bash
   git commit -m 'Add some AmazingFeature'
   ```
4. **Push to the Branch**
   ```bash
   git push origin feature/AmazingFeature
   ```
5. **Open a Pull Request**

Please try to follow the existing code style and Angular best practices.

## License

Distributed under the MIT License. See `LICENSE` file for more information.
