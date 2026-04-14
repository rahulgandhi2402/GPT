import React, { useState, useRef } from 'react';
import { Upload, FileDown, X, CheckCircle } from 'lucide-react';

const DashboardToPDF = () => {
  const [images, setImages] = useState([null, null]);
  const [previews, setPreviews] = useState([null, null]);
  const [taskbarHeight, setTaskbarHeight] = useState(40);
  const fileInputRefs = [useRef(null), useRef(null)];

  const handleImageUpload = (index, e) => {
    const file = e.target.files[0];
    if (file && file.type.startsWith('image/')) {
      const reader = new FileReader();
      reader.onload = (event) => {
        const img = new Image();
        img.onload = () => {
          const newImages = [...images];
          const newPreviews = [...previews];
          newImages[index] = img;
          newPreviews[index] = event.target.result;
          setImages(newImages);
          setPreviews(newPreviews);
        };
        img.src = event.target.result;
      };
      reader.readAsDataURL(file);
    }
  };

  const removeImage = (index) => {
    const newImages = [...images];
    const newPreviews = [...previews];
    newImages[index] = null;
    newPreviews[index] = null;
    setImages(newImages);
    setPreviews(newPreviews);
    if (fileInputRefs[index].current) {
      fileInputRefs[index].current.value = '';
    }
  };

  const cropTaskbar = (img, canvas) => {
    const ctx = canvas.getContext('2d');
    const cropHeight = img.height - taskbarHeight;
    canvas.width = img.width;
    canvas.height = cropHeight;
    ctx.drawImage(img, 0, 0, img.width, cropHeight, 0, 0, img.width, cropHeight);
  };

  const generatePDF = async () => {
    if (!images[0] || !images[1]) {
      alert('Please upload both images first!');
      return;
    }

    try {
      // Load jsPDF from CDN
      const script = document.createElement('script');
      script.src = 'https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js';
      document.head.appendChild(script);

      script.onload = () => {
        const { jsPDF } = window.jspdf;

        // Create canvases for cropping
        const canvas1 = document.createElement('canvas');
        const canvas2 = document.createElement('canvas');

        cropTaskbar(images[0], canvas1);
        cropTaskbar(images[1], canvas2);

        // Get cropped image data
        const img1Data = canvas1.toDataURL('image/jpeg', 0.95);
        const img2Data = canvas2.toDataURL('image/jpeg', 0.95);

        // Calculate dimensions
        const img1Width = canvas1.width;
        const img1Height = canvas1.height;
        const img2Width = canvas2.width;
        const img2Height = canvas2.height;

        // Determine orientation based on first image
        const orientation = img1Width > img1Height ? 'landscape' : 'portrait';

        // Create PDF
        const pdf = new jsPDF({
          orientation: orientation,
          unit: 'px',
          format: [img1Width, img1Height]
        });

        // Add first image
        pdf.addImage(img1Data, 'JPEG', 0, 0, img1Width, img1Height);

        // Add second page
        pdf.addPage([img2Width, img2Height], img2Width > img2Height ? 'landscape' : 'portrait');
        pdf.addImage(img2Data, 'JPEG', 0, 0, img2Width, img2Height);

        // Save PDF
        pdf.save('Performance_Dashboard_Q1_FY2025.pdf');
      };
    } catch (error) {
      console.error('Error generating PDF:', error);
      alert('Error generating PDF. Please try again.');
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 p-6">
      <div className="max-w-6xl mx-auto">
        <div className="bg-white rounded-xl shadow-xl p-8 mb-6">
          <h1 className="text-3xl font-bold text-gray-800 mb-2">Dashboard to PDF Converter</h1>
          <p className="text-gray-600">
            Upload your dashboard screenshots and convert them to a professional PDF
          </p>
        </div>

        <div className="bg-white rounded-xl shadow-xl p-8 mb-6">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-xl font-semibold text-gray-800">Settings</h2>
          </div>

          <div className="mb-6">
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Taskbar Height (pixels to crop from bottom)
            </label>
            <input
              type="number"
              value={taskbarHeight}
              onChange={(e) => setTaskbarHeight(parseInt(e.target.value) || 0)}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              min="0"
              max="200"
            />
            <p className="text-xs text-gray-500 mt-1">Default: 40 pixels. Adjust if needed.</p>
          </div>
        </div>

        <div className="grid md:grid-cols-2 gap-6 mb-6">
          {[0, 1].map((index) => (
            <div key={index} className="bg-white rounded-xl shadow-xl p-6">
              <h3 className="text-lg font-semibold text-gray-800 mb-4">
                Dashboard Image {index + 1}
              </h3>

              {!previews[index] ? (
                <label className="flex flex-col items-center justify-center w-full h-64 border-2 border-dashed border-gray-300 rounded-lg cursor-pointer hover:border-blue-500 hover:bg-blue-50 transition-colors">
                  <div className="flex flex-col items-center justify-center pt-5 pb-6">
                    <Upload className="w-12 h-12 text-gray-400 mb-3" />
                    <p className="mb-2 text-sm text-gray-500 font-semibold">Click to upload</p>
                    <p className="text-xs text-gray-500">PNG, JPG up to 10MB</p>
                  </div>
                  <input
                    ref={fileInputRefs[index]}
                    type="file"
                    className="hidden"
                    accept="image/*"
                    onChange={(e) => handleImageUpload(index, e)}
                  />
                </label>
              ) : (
                <div className="relative">
                  <img
                    src={previews[index]}
                    alt={`Dashboard ${index + 1}`}
                    className="w-full h-auto rounded-lg border border-gray-200"
                  />
                  <button
                    onClick={() => removeImage(index)}
                    className="absolute top-2 right-2 bg-red-500 hover:bg-red-600 text-white rounded-full p-2 shadow-lg transition-colors"
                  >
                    <X size={16} />
                  </button>
                  <div className="mt-2 flex items-center text-sm text-green-600">
                    <CheckCircle size={16} className="mr-1" />
                    Image uploaded successfully
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>

        <div className="bg-white rounded-xl shadow-xl p-8">
          <button
            onClick={generatePDF}
            disabled={!images[0] || !images[1]}
            className={`w-full flex items-center justify-center gap-3 py-4 px-6 rounded-lg font-semibold text-lg transition-all ${
              images[0] && images[1]
                ? 'bg-blue-600 hover:bg-blue-700 text-white shadow-lg hover:shadow-xl'
                : 'bg-gray-300 text-gray-500 cursor-not-allowed'
            }`}
          >
            <FileDown size={24} />
            Generate PDF
          </button>

          {(!images[0] || !images[1]) && (
            <p className="text-center text-sm text-gray-500 mt-4">
              Please upload both dashboard images to generate the PDF
            </p>
          )}
        </div>

        <div className="mt-6 bg-blue-50 border border-blue-200 rounded-xl p-6">
          <h3 className="font-semibold text-blue-900 mb-2">📌 Instructions:</h3>
          <ul className="text-sm text-blue-800 space-y-1">
            <li>1. Upload your first dashboard screenshot</li>
            <li>2. Upload your second dashboard screenshot</li>
            <li>3. Adjust taskbar height if needed (default: 40px)</li>
            <li>4. Click "Generate PDF" to download your merged document</li>
            <li>5. The taskbar will be automatically removed from both images</li>
          </ul>
        </div>
      </div>
    </div>
  );
};

export default DashboardToPDF;
